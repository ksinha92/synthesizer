"""Pub/sub helpers for job progress events.

Workers publish to Redis channels; the SSE endpoint subscribes. Falls back
gracefully when Redis is unavailable — `publish_progress` never raises so
it is safe to call from Celery worker context (worst case is the SSE client
falls back to DB polling on the read side).

Channel naming: ``job:<job_id>:progress``.
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

import structlog

logger = structlog.get_logger(__name__)


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def channel_for(job_id: str) -> str:
    """Return the pub/sub channel name for a given job id."""
    return f"job:{job_id}:progress"


def publish_progress(job_id: str, payload: dict[str, Any]) -> bool:
    """Publish a progress event to Redis.

    Returns ``True`` on success, ``False`` on any error. Never raises —
    designed to be safe to call from Celery workers where a Redis hiccup
    must not crash the task.
    """
    try:
        import redis  # sync client OK for Celery worker context

        client = redis.from_url(
            _redis_url(),
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.publish(channel_for(job_id), json.dumps(payload, default=str))
        return True
    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        logger.debug(
            "publish_progress_failed",
            job_id=job_id,
            error=str(exc),
        )
        return False


async def subscribe_progress(job_id: str) -> AsyncIterator[dict[str, Any]]:
    """Async generator yielding progress events from Redis.

    Raises ``ConnectionError`` (or any underlying redis error) if Redis is
    unreachable so the caller can fall back to DB polling. Subscribes on the
    channel returned by :func:`channel_for` and yields each decoded JSON
    payload until the subscriber is cancelled or the connection closes.
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url(
        _redis_url(),
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel_for(job_id))
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            try:
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode("utf-8")
                yield json.loads(data)
            except (TypeError, ValueError):
                continue
    finally:
        try:
            await pubsub.unsubscribe(channel_for(job_id))
            await pubsub.close()
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
