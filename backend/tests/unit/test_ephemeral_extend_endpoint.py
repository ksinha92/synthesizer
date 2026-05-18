"""Unit tests for ``POST /ephemeral/{id}/extend`` (Phase 61 F18).

The extend endpoint pushes ``expires_at`` out by ``additional_hours``,
clamping the new value at ``created_at + 30 days``. We exercise the
handler function directly to keep the test fast -- the dependency
injection happens at FastAPI routing time, not inside the function
body, so we just pass the mocks ourselves.

Two cases:

* Valid extension within the 30-day cap returns 200 + the updated
  ``expires_at``.
* Extension that would exceed the cap returns 400 with the right
  error envelope.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.ephemeral import EphemeralExtend, extend_ephemeral


def _make_env(created_delta: timedelta = timedelta(days=2), ttl_days: int = 7):
    """Build an ``EphemeralEnvironmentModel`` stand-in.

    Defaults: created 2 days ago, expires in 5 days (so 7-day TTL has
    used 2 days). Room to extend up to 23 days before hitting the
    30-day cap from creation.
    """
    now = datetime.now(timezone.utc)
    created_at = now - created_delta
    expires_at = created_at + timedelta(days=ttl_days)
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="my-env",
        source_job_id=None,
        destination_connection_id=None,
        schema_name="sch",
        status="ready",
        expires_at=expires_at,
        created_by=uuid.uuid4(),
        created_at=created_at,
        updated_at=now,
        container_id="abc",
        host_port=40123,
        connection_string="postgresql+asyncpg://...",
    )


def _session_returning(env) -> MagicMock:
    """Build a session whose first SELECT returns the supplied env row."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = env

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session


def test_extend_within_cap_returns_updated_expiry():
    """Adding 24h to a 5-day-remaining env stays inside the 30-day cap."""
    env = _make_env()
    original_expires = env.expires_at
    session = _session_returning(env)

    response = asyncio.run(
        extend_ephemeral(
            project_id=env.project_id,
            ephemeral_id=env.id,
            body=EphemeralExtend(additional_hours=24),
            current_user={"id": str(uuid.uuid4()), "role": "admin"},
            session=session,
            _member={"id": "u"},
        )
    )

    assert env.expires_at == original_expires + timedelta(hours=24)
    # The response carries the updated expiry, serialised.
    assert response.expires_at == env.expires_at.isoformat()


def test_extend_exceeding_cap_returns_400():
    """Pushing total TTL past 30 days from creation must raise 400."""
    # Created 25 days ago, TTL was 30 days -> 5 days left. Asking for
    # 10 more days would exceed the 30-day cap from creation.
    env = _make_env(created_delta=timedelta(days=25), ttl_days=30)
    session = _session_returning(env)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            extend_ephemeral(
                project_id=env.project_id,
                ephemeral_id=env.id,
                body=EphemeralExtend(additional_hours=24 * 10),
                current_user={"id": str(uuid.uuid4()), "role": "admin"},
                session=session,
                _member={"id": "u"},
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "ttl_cap_exceeded"


def test_extend_on_revoked_env_returns_400():
    """Extending a ``revoked`` env makes no sense -- handler must reject."""
    env = _make_env()
    env.status = "revoked"
    session = _session_returning(env)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            extend_ephemeral(
                project_id=env.project_id,
                ephemeral_id=env.id,
                body=EphemeralExtend(additional_hours=24),
                current_user={"id": str(uuid.uuid4()), "role": "admin"},
                session=session,
                _member={"id": "u"},
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_state"


def test_extend_missing_env_returns_404():
    """When the row doesn't exist, handler must surface 404."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            extend_ephemeral(
                project_id=uuid.uuid4(),
                ephemeral_id=uuid.uuid4(),
                body=EphemeralExtend(additional_hours=24),
                current_user={"id": str(uuid.uuid4()), "role": "admin"},
                session=session,
                _member={"id": "u"},
            )
        )

    assert exc_info.value.status_code == 404
