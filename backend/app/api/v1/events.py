"""SSE streaming for real-time job progress.

Phase 59 F13: prefer Redis pub/sub over DB polling. The worker publishes a
progress event on ``job:<job_id>:progress`` after each status/progress
update. The SSE endpoint subscribes to that channel and yields events as
they arrive. If Redis is unreachable we transparently fall back to the
original 2-second DB poll so the endpoint keeps working in degraded mode.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.infrastructure.auth.jwt import decode_token
from app.infrastructure.auth.rbac import assert_project_access
from app.infrastructure.messaging.progress_pubsub import subscribe_progress
from app.infrastructure.persistence.database import async_session_factory
from app.infrastructure.persistence.models.job import JobModel
from app.infrastructure.persistence.models.user import UserModel

logger = structlog.get_logger()
router = APIRouter(tags=["events"])

TERMINAL_STATUSES = {
    "completed",
    "completed_with_warnings",
    "failed",
    "cancelled",
}
HEARTBEAT_INTERVAL = 30.0  # seconds — matches pre-F13 cadence
DB_POLL_INTERVAL = 2.0  # seconds — fallback when Redis is down


@router.get("/projects/{project_id}/jobs/{job_id}/stream")
async def stream_job_progress(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    request: Request,
    token: str | None = Query(None, description="JWT token for authentication (optional, also accepts cookies)"),
):
    """SSE endpoint for real-time job progress. Auth via ?token= query param or cookie."""
    # Accept token from query param OR cookie
    auth_token = token or request.cookies.get("access_token")
    if not auth_token:
        raise HTTPException(401, "Authentication required")

    try:
        payload = decode_token(auth_token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Invalid token")
    except HTTPException:
        raise
    except Exception as exc:
        await logger.awarning(
            "sse_token_invalid",
            reason=type(exc).__name__,
            job_id=str(job_id),
            project_id=str(project_id),
        )
        raise HTTPException(401, "Invalid or expired token")

    # Verify job exists, belongs to project, AND that the user has membership.
    async with async_session_factory() as session:
        # Resolve full user record so assert_project_access has role + id.
        user_row = await session.execute(select(UserModel).where(UserModel.id == uuid.UUID(user_id)))
        user = user_row.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(401, "User not found or disabled")
        current_user = {"id": str(user.id), "email": user.email, "role": user.role}

        try:
            await assert_project_access(project_id, current_user, session, "viewer")
        except HTTPException:
            raise

        result = await session.execute(
            select(JobModel).where(JobModel.id == job_id, JobModel.project_id == project_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(404, "Job not found")

    return StreamingResponse(
        _progress_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _progress_stream(job_id: uuid.UUID):
    """Yield SSE events for ``job_id``.

    Strategy:
      0. Emit one initial snapshot of the current ``JobModel`` state from DB.
         Redis pub/sub only delivers messages published AFTER subscribe — a
         client opening the stream after the last progress event (especially
         after a job has already completed) would otherwise only see
         heartbeats and never the terminal status. The snapshot also lets
         us short-circuit when the job is already terminal.
      1. Try Redis pub/sub via :func:`subscribe_progress`. Each message is
         forwarded immediately as an SSE event.
      2. If the Redis subscriber raises (connection refused, network error,
         redis package missing, etc.) fall back to the legacy 2 s DB poll.
      3. In either branch we yield a heartbeat ping every ~30 s of silence
         so proxies/clients don't drop the long-lived connection.
    """
    yield "retry: 3000\n\n"

    # --- Snapshot of current state (must precede Redis subscribe) -----------
    snapshot = await _current_state_snapshot(job_id)
    if snapshot is not None:
        yield f"data: {json.dumps(snapshot)}\n\n"
        if snapshot.get("status") in TERMINAL_STATUSES:
            # Already done — nothing for Redis/DB-poll to add.
            return

    # --- Redis path ---------------------------------------------------------
    try:
        async for event in _redis_event_stream(job_id):
            yield event
            # Caller signalled terminal — close cleanly.
            if event.startswith("data: ") and _is_terminal_event(event):
                return
        # Generator exited cleanly without a terminal — fall through to DB
        # poll so we don't strand the client.
    except Exception as exc:  # noqa: BLE001
        await logger.ainfo(
            "redis_unavailable_falling_back_to_db_poll",
            job_id=str(job_id),
            error=str(exc),
        )

    # --- DB-poll fallback ---------------------------------------------------
    async for event in _db_poll_event_stream(job_id):
        yield event


async def _current_state_snapshot(job_id: uuid.UUID) -> dict | None:
    """Read the current ``JobModel`` state and return an SSE payload dict.

    Returns ``None`` if the row vanished between auth and stream start
    (caller will simply skip emitting and fall through to Redis/DB-poll).
    """
    try:
        async with async_session_factory() as session:
            row = (
                await session.execute(
                    select(JobModel).where(JobModel.id == job_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return {
                "status": row.status,
                "progress": row.progress or 0,
                "result_summary": row.result_summary,
            }
    except Exception as exc:  # noqa: BLE001
        await logger.awarning(
            "sse_snapshot_failed", job_id=str(job_id), error=str(exc)
        )
        return None


async def _redis_event_stream(job_id: uuid.UUID):
    """Adapt the Redis async generator into SSE-formatted strings.

    Wraps :func:`subscribe_progress` with a 30 s read timeout — when no
    message arrives we emit a heartbeat comment line so the connection
    stays warm.
    """
    sub = subscribe_progress(str(job_id))
    try:
        while True:
            try:
                payload = await asyncio.wait_for(sub.__anext__(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                # No message in 30 s — send heartbeat and keep waiting.
                yield ": ping\n\n"
                continue
            except StopAsyncIteration:
                return

            yield f"data: {json.dumps(payload)}\n\n"
            if payload.get("status") in TERMINAL_STATUSES:
                return
    finally:
        # Make sure the underlying pubsub generator is cleaned up.
        try:
            await sub.aclose()  # type: ignore[func-returns-value]
        except Exception:  # noqa: BLE001
            pass


def _is_terminal_event(event: str) -> bool:
    """Quick check on the serialized SSE event for a terminal status."""
    for status in TERMINAL_STATUSES:
        if f'"status": "{status}"' in event or f'"status":"{status}"' in event:
            return True
    return False


async def _db_poll_event_stream(job_id: uuid.UUID):
    """Original 2-second DB polling loop. Used as a fallback when Redis is
    unavailable so the SSE endpoint keeps working in degraded mode."""
    last_progress = -1
    seconds_since_event = 0.0
    while True:
        try:
            progress_data = await _poll_job_status(job_id)
            if (
                progress_data["progress"] != last_progress
                or progress_data["status"] in TERMINAL_STATUSES
            ):
                last_progress = progress_data["progress"]
                yield f"data: {json.dumps(progress_data)}\n\n"
                seconds_since_event = 0.0

            if progress_data["status"] in TERMINAL_STATUSES:
                return

            await asyncio.sleep(DB_POLL_INTERVAL)
            seconds_since_event += DB_POLL_INTERVAL
            if seconds_since_event >= HEARTBEAT_INTERVAL:
                yield ": ping\n\n"
                seconds_since_event = 0.0
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            return


async def _poll_job_status(job_id: uuid.UUID) -> dict:
    """Poll job status from database."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(JobModel).where(JobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return {"status": "not_found", "progress": 0}

        return {
            "job_id": str(job.id),
            "status": job.status,
            "progress": job.progress,
            "error_message": job.error_message,
            "message": (job.checkpoint or {}).get("message", ""),
        }
