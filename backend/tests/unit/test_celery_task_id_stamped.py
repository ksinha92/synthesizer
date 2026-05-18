"""Phase 59 F9 — workers stamp ``JobModel.celery_task_id`` on start.

Stamping the Celery task id onto the row is the prerequisite for
cancel-by-Celery-id and for the DLQ rehydration path that links a
failed job back to its task. Each worker task pulls the JobModel and
writes ``self.request.id`` into the field before doing real work.

We exercise the masking task here as a representative case — the same
pattern lives in every worker file (discovery, synthetic, file-set,
subsetting, workflow). Mocking the full async session is fiddly, so we
test the *minimum slice* that demonstrates the stamping decision: when
the loaded JobModel has no ``celery_task_id``, the worker assigns
``task.request.id`` onto it.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


class _AsyncCM:
    """Tiny async-context-manager wrapper around a mock session."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_session(job_row) -> MagicMock:
    """Build a session mock that satisfies the masking task's early code path."""
    session = MagicMock()
    session.get = AsyncMock(return_value=job_row)
    # Force an early bail-out: rules lookup raises so we never reach the
    # connector / engine path. The except block already handles failure
    # via the error-session factory we also patch out.
    session.execute = AsyncMock(side_effect=RuntimeError("bail-out for test"))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def test_celery_task_id_stamped_on_running_transition() -> None:
    """When a fresh job hits a worker, ``celery_task_id`` is set to ``task.request.id``.

    We patch the async-session factory to return our pre-baked mock
    session, and short-circuit the error-path side effects so the test
    stays focused on the stamping behavior.
    """
    from app.infrastructure.messaging import masking_tasks

    job_uuid = uuid.uuid4()
    policy_uuid = uuid.uuid4()
    connection_uuid = uuid.uuid4()
    project_uuid = uuid.uuid4()

    # Job row starts with no celery_task_id — the worker must populate it.
    job_row = SimpleNamespace(
        id=job_uuid,
        celery_task_id=None,
        progress=0,
        status="pending",
    )
    session = _make_session(job_row)

    err_session = MagicMock()
    err_session.execute = AsyncMock()
    err_session.commit = AsyncMock()

    def _factory():
        # First call (main session) returns our stamping session; subsequent
        # calls (error path) hand back a no-op session so the bail-out write
        # doesn't NPE on a missing context manager.
        if _factory.calls == 0:
            _factory.calls += 1
            return _AsyncCM(session)
        return _AsyncCM(err_session)

    _factory.calls = 0

    task = SimpleNamespace(
        request=SimpleNamespace(id="celery-task-abc-123", retries=0),
        retry=lambda exc: (_ for _ in ()).throw(exc),  # propagate so we catch RuntimeError below
    )

    with patch.object(
        masking_tasks,
        "async_session_factory",
        _factory,
        create=True,
    ), patch(
        "app.infrastructure.persistence.database.async_session_factory",
        _factory,
    ), patch(
        "app.infrastructure.messaging.celery_app.fire_webhooks",
        new=AsyncMock(),
    ), patch(
        "app.infrastructure.messaging.progress_pubsub.publish_progress",
        new=MagicMock(return_value=True),
    ):
        # The masking task re-imports async_session_factory inside the
        # function body, so we also patch the module-level reference.
        try:
            asyncio.run(
                masking_tasks._run_masking_async(
                    task,
                    str(policy_uuid),
                    str(connection_uuid),
                    str(project_uuid),
                    str(job_uuid),
                )
            )
        except RuntimeError:
            # Expected — the bail-out side_effect propagates through retry.
            pass

    # The stamping happens before the bail-out, so even though the rest
    # of the task crashed, celery_task_id must already be set.
    assert job_row.celery_task_id == "celery-task-abc-123"


def test_celery_task_id_not_overwritten_when_already_present() -> None:
    """A re-run / replayed task must not clobber an existing ``celery_task_id``.

    The stamp guard is ``if not job.celery_task_id`` — once a task id is
    on the row, retries leave it alone.
    """
    from app.infrastructure.messaging import masking_tasks

    job_uuid = uuid.uuid4()
    policy_uuid = uuid.uuid4()
    connection_uuid = uuid.uuid4()
    project_uuid = uuid.uuid4()

    job_row = SimpleNamespace(
        id=job_uuid,
        celery_task_id="original-task-id-from-first-attempt",
        progress=10,
        status="running",
    )
    session = _make_session(job_row)

    err_session = MagicMock()
    err_session.execute = AsyncMock()
    err_session.commit = AsyncMock()

    def _factory():
        if _factory.calls == 0:
            _factory.calls += 1
            return _AsyncCM(session)
        return _AsyncCM(err_session)

    _factory.calls = 0

    task = SimpleNamespace(
        request=SimpleNamespace(id="retry-task-id-different", retries=1),
        retry=lambda exc: (_ for _ in ()).throw(exc),
    )

    with patch.object(
        masking_tasks,
        "async_session_factory",
        _factory,
        create=True,
    ), patch(
        "app.infrastructure.persistence.database.async_session_factory",
        _factory,
    ), patch(
        "app.infrastructure.messaging.celery_app.fire_webhooks",
        new=AsyncMock(),
    ), patch(
        "app.infrastructure.messaging.progress_pubsub.publish_progress",
        new=MagicMock(return_value=True),
    ):
        try:
            asyncio.run(
                masking_tasks._run_masking_async(
                    task,
                    str(policy_uuid),
                    str(connection_uuid),
                    str(project_uuid),
                    str(job_uuid),
                )
            )
        except RuntimeError:
            pass

    assert job_row.celery_task_id == "original-task-id-from-first-attempt"
