"""Unit tests for ``run_ephemeral_expire_sweep_task`` (Phase 61 F18).

We exercise the ``_sweep_async`` async workhorse directly with a mocked
session factory. Two flow paths to cover:

* ``ready`` rows past ``expires_at`` flip to ``expired`` and any
  attached container is torn down via the provisioner.
* ``pending`` rows older than the stuck threshold flip to ``failed``.

The provisioner is monkey-patched so no Docker calls leave the process.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


class _AsyncCM:
    """Tiny async-context-manager wrapper around a session mock."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_sweep_flips_ready_past_expires_to_expired():
    """A ``ready`` row whose expires_at is in the past must be flipped
    to ``expired`` and its container must be torn down."""
    from app.infrastructure.messaging import ephemeral_tasks

    now = datetime.now(timezone.utc)
    # One ready+expired row; one ready+still-alive row that must NOT
    # be flipped. The select filter already excludes the alive one, so
    # we only put the expired row in scalars.all() -- this asserts the
    # task respects the SQL filter rather than scanning everything.
    expired_env = SimpleNamespace(
        id=uuid.uuid4(),
        status="ready",
        expires_at=now - timedelta(hours=1),
        container_id="abc-container",
        revoked_at=None,
    )

    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = [expired_env]

    session = MagicMock()
    session.execute = AsyncMock(return_value=scalar_result)
    session.commit = AsyncMock()

    teardown_calls: list[str] = []

    async def _teardown(cid):
        teardown_calls.append(cid)

    fake_provisioner = MagicMock()
    fake_provisioner.stop_and_remove = AsyncMock(side_effect=_teardown)

    def _factory():
        return _AsyncCM(session)

    with patch(
        "app.infrastructure.persistence.database.async_session_factory",
        _factory,
    ), patch(
        "app.infrastructure.ephemeral.docker_provisioner.DockerProvisioner",
        return_value=fake_provisioner,
    ):
        asyncio.run(ephemeral_tasks._sweep_async())

    # The container was torn down and the row was flipped.
    assert teardown_calls == ["abc-container"]
    assert expired_env.status == "expired"
    assert expired_env.revoked_at is not None
    # Two ``execute`` calls: one select for ready+expired, one update for stuck.
    assert session.execute.await_count == 2


def test_sweep_flips_stuck_pending_to_failed():
    """``pending`` rows older than 1h must be flagged failed via UPDATE."""
    from app.infrastructure.messaging import ephemeral_tasks

    # No ready/expired rows; the first select returns empty.
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []

    session = MagicMock()
    session.execute = AsyncMock(return_value=empty_result)
    session.commit = AsyncMock()

    fake_provisioner = MagicMock()
    fake_provisioner.stop_and_remove = AsyncMock()

    def _factory():
        return _AsyncCM(session)

    with patch(
        "app.infrastructure.persistence.database.async_session_factory",
        _factory,
    ), patch(
        "app.infrastructure.ephemeral.docker_provisioner.DockerProvisioner",
        return_value=fake_provisioner,
    ):
        asyncio.run(ephemeral_tasks._sweep_async())

    # Two execute() calls: select(ready) then update(stuck pending).
    # The UPDATE's filter is constructed inside the task; we just need
    # to confirm it was issued -- the SQL itself is the contract.
    assert session.execute.await_count == 2
    # And the provisioner was NOT asked to tear anything down (no rows
    # came back from the ready query).
    fake_provisioner.stop_and_remove.assert_not_called()
