"""
Async SQLAlchemy session factory and Redis connection pool.

Provides:
  - `AsyncSessionLocal` — async session factory
  - `get_db()` — FastAPI dependency yielding a session per request
  - `get_redis()` — FastAPI dependency for Redis client
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# ─── PostgreSQL ────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,  # Detect stale connections
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep instances usable after commit
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: yields an async DB session per request.

    Usage::

        @router.get("/agents")
        async def list_agents(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ─── Redis ────────────────────────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis_pool() -> aioredis.Redis:
    """Return the global Redis connection pool (created on first call)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    FastAPI dependency: yields the shared Redis client.

    Usage::

        @router.post("/run")
        async def start_run(redis: aioredis.Redis = Depends(get_redis)):
            await redis.set("key", "value")
    """
    redis = await get_redis_pool()
    yield redis


async def close_db() -> None:
    """Dispose engine connections — called on app shutdown."""
    await engine.dispose()


async def close_redis() -> None:
    """Close Redis connection pool — called on app shutdown."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
