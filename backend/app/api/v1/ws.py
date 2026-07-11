"""
WebSocket API — Real-time trace streaming for agent runs.

Clients connect to WS /api/v1/ws/runs/{run_id} to receive live
trace events as the engine executes steps.

The engine publishes events to a Redis Pub/Sub channel:
  channel: agentcraft:trace:{run_id}

This handler subscribes to that channel and forwards events to the
connected WebSocket client.
"""

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

log = structlog.get_logger()
router = APIRouter(tags=["WebSocket"])

# Track active connections per run: run_id → list of WebSocket
_connections: dict[str, list[WebSocket]] = {}


@router.websocket("/ws/runs/{run_id}")
async def run_trace_ws(run_id: str, websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time agent execution tracing.

    Protocol:
      1. Client connects, sends auth token as first message: {"token": "..."}
      2. Server validates token and subscribes to the run's Redis channel
      3. Server streams trace events as JSON objects until run completes
      4. Client can send {"type": "ping"} for keepalive

    Event types streamed:
      - step_start, step_end, llm_stream, tool_called
      - hitl_required, memory_retrieved, run_complete, run_error
    """
    await websocket.accept()

    # Register connection
    if run_id not in _connections:
        _connections[run_id] = []
    _connections[run_id].append(websocket)

    log.info("ws.connected", run_id=run_id, connections=len(_connections[run_id]))

    try:
        # Import here to avoid circular imports at module level
        from app.db.session import get_redis_pool

        redis = await get_redis_pool()
        pubsub = redis.pubsub()
        channel = f"agentcraft:trace:{run_id}"
        await pubsub.subscribe(channel)

        # Listen for Redis messages and forward to WebSocket
        async def listen_redis() -> None:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"])
                    except WebSocketDisconnect:
                        break

        # Listen for WebSocket pings from client
        async def listen_ws() -> None:
            while True:
                try:
                    data = await websocket.receive_text()
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except (WebSocketDisconnect, json.JSONDecodeError):
                    break

        # Run both listeners concurrently until one finishes (e.g., disconnect)
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(listen_redis()),
                asyncio.create_task(listen_ws()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        log.info("ws.disconnected", run_id=run_id)
    except Exception as exc:
        log.error("ws.error", run_id=run_id, error=str(exc))
    finally:
        if run_id in _connections:
            _connections[run_id].remove(websocket)
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass


async def broadcast_trace_event(redis, run_id: str, event: dict) -> None:
    """
    Publish a trace event to the Redis Pub/Sub channel for this run.

    Called by the engine after every step.
    """
    channel = f"agentcraft:trace:{run_id}"
    await redis.publish(channel, json.dumps(event))
