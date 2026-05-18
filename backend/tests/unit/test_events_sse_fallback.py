"""SSE fallback behavior when Redis pub/sub is unavailable (Phase 59 F13)."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest

from app.api.v1 import events as events_module


def _collect(agen, *, max_events: int = 10, timeout: float = 1.0):
    """Drain an async generator into a list with a hard cap + timeout."""

    async def runner():
        out: list[str] = []
        try:
            async for ev in agen:
                out.append(ev)
                if len(out) >= max_events:
                    break
        except Exception:  # noqa: BLE001 — test boundary
            pass
        return out

    return asyncio.run(asyncio.wait_for(runner(), timeout=timeout))


@pytest.mark.asyncio
async def test_progress_stream_falls_back_to_db_poll_when_redis_raises():
    """If ``_redis_event_stream`` raises immediately, the generator must
    transparently switch to the DB-poll generator and yield from it."""

    job_id = uuid.uuid4()

    async def _exploding_redis_stream(_):
        raise ConnectionError("redis down")
        yield  # pragma: no cover — needed to make this an async generator

    # DB poll yields a single completed event then stops.
    async def _fake_db_poll(_):
        yield 'data: {"status": "completed", "progress": 100}\n\n'

    with patch.object(events_module, "_redis_event_stream", _exploding_redis_stream), patch.object(
        events_module, "_db_poll_event_stream", _fake_db_poll
    ):
        events: list[str] = []
        async for ev in events_module._progress_stream(job_id):
            events.append(ev)
            if len(events) >= 5:
                break

    # First event must be the "retry: 3000" preamble.
    assert events[0].startswith("retry:")
    # Fallback event must have been forwarded from the DB-poll stream.
    assert any("completed" in e for e in events), events


@pytest.mark.asyncio
async def test_progress_stream_prefers_redis_when_available():
    """Happy path: when Redis yields a terminal event, the DB-poll path is
    never invoked."""

    job_id = uuid.uuid4()
    db_poll_invocations = {"count": 0}

    async def _ok_redis_stream(_):
        yield 'data: {"status": "running", "progress": 50}\n\n'
        yield 'data: {"status": "completed", "progress": 100}\n\n'

    async def _spy_db_poll(_):
        db_poll_invocations["count"] += 1
        if False:  # pragma: no cover
            yield ""

    with patch.object(events_module, "_redis_event_stream", _ok_redis_stream), patch.object(
        events_module, "_db_poll_event_stream", _spy_db_poll
    ):
        events: list[str] = []
        async for ev in events_module._progress_stream(job_id):
            events.append(ev)
            if len(events) >= 5:
                break

    assert any("running" in e for e in events)
    assert any("completed" in e for e in events)
    assert db_poll_invocations["count"] == 0, "DB poll must not run when Redis succeeds"
