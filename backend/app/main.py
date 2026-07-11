"""
AgentCraft FastAPI Application — Entry Point

Configures:
  - FastAPI app with metadata
  - CORS middleware
  - Structured JSON logging (structlog)
  - Startup/shutdown lifecycle events (DB pool, Redis, engine worker)
  - All API routers
  - Background engine worker (consumes Redis Streams run queue)
  - Global exception handlers
"""

import asyncio
import json
import uuid

import structlog
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.config import settings
from app.db.session import close_db, close_redis, get_redis_pool

# Configure structlog for JSON output in production, pretty in dev
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()

# ─── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="AgentCraft API",
    description="Enterprise-Grade Agentic AI Platform — REST + WebSocket API",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    default_response_class=ORJSONResponse,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

from app.api.v1 import auth, agents, workflows, runs, ws, memory, tools  # noqa: E402

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(agents.router, prefix=settings.api_prefix)
app.include_router(workflows.router, prefix=settings.api_prefix)
app.include_router(runs.router, prefix=settings.api_prefix)
app.include_router(ws.router, prefix=settings.api_prefix)
app.include_router(memory.router, prefix=settings.api_prefix)
app.include_router(tools.router, prefix=settings.api_prefix)

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "version": settings.app_version}


# ─── Lifecycle ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    """Initialize connections and start the engine worker."""
    log.info("app.startup", version=settings.app_version, env=settings.environment)

    # Verify Redis connection
    try:
        redis = await get_redis_pool()
        await redis.ping()
        log.info("redis.connected", url=settings.redis_url)
    except Exception as exc:
        log.error("redis.connection_failed", error=str(exc))

    # Start the engine worker background task
    asyncio.create_task(_engine_worker(), name="engine_worker")
    log.info("engine_worker.started")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Graceful shutdown — close all connections."""
    log.info("app.shutdown")
    await close_db()
    await close_redis()


# ─── Engine Worker (Redis Streams Consumer) ───────────────────────────────────

async def _engine_worker() -> None:
    """
    Background task: consumes runs from the Redis Streams queue
    and executes them via AgentCraftEngine.

    This runs in the same process for simplicity. In production,
    extract this into a separate worker process or use Celery/ARQ.

    Queue: agentcraft:run_queue (Redis Stream)
    Consumer group: engine-workers
    """
    from app.core.engine import AgentCraftEngine
    from app.db.session import AsyncSessionLocal

    redis = await get_redis_pool()
    stream = "agentcraft:run_queue"
    group = "engine-workers"
    consumer = "worker-1"

    # Create consumer group (idempotent)
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception:
        pass  # Group already exists

    log.info("engine_worker.listening", stream=stream)

    while True:
        try:
            # Block-read up to 10 messages, wait 2s for new ones
            messages = await redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=5,
                block=2000,
            )

            if not messages:
                continue

            for stream_name, entries in messages:
                for message_id, fields in entries:
                    run_id_str = fields.get("run_id", "")
                    if not run_id_str:
                        await redis.xack(stream, group, message_id)
                        continue

                    log.info("engine_worker.processing", run_id=run_id_str)

                    try:
                        async with AsyncSessionLocal() as db:
                            engine = AgentCraftEngine(db=db, redis=redis)
                            await engine.execute_run(uuid.UUID(run_id_str))
                    except Exception as exc:
                        log.error("engine_worker.run_error", run_id=run_id_str, error=str(exc))

                    # Acknowledge message
                    await redis.xack(stream, group, message_id)

        except asyncio.CancelledError:
            log.info("engine_worker.stopped")
            break
        except Exception as exc:
            log.error("engine_worker.error", error=str(exc))
            await asyncio.sleep(5)  # Back off on unexpected errors


# ─── Global Exception Handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    log.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"},
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # Structlog handles logging
    )
