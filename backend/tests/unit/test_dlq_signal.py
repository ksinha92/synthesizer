"""Unit tests for the ``task_failure`` -> DLQ signal handler.

Phase 59 F8. The handler is registered against Celery's ``task_failure``
signal in ``app.infrastructure.messaging.celery_app`` and inserts a
``DeadLetterJobModel`` row only once a task has exhausted its retries.

These tests exercise the handler directly (it is a plain function under the
hood) with a fabricated ``sender`` and a patched sync-session factory so we
never touch a real database or a real Celery worker.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.infrastructure.messaging.celery_app import _handle_task_failure_to_dlq


def _make_sender(name: str = "app.infrastructure.messaging.masking_tasks.run_masking_task",
                 max_retries: int = 2,
                 retries: int = 0,
                 run_fn=None) -> SimpleNamespace:
    """Build a fake Celery task ``sender`` object.

    The real ``Task`` instance exposes ``name``, ``max_retries``,
    ``request.retries``, and ``run`` (the wrapped task function whose
    signature the handler introspects to find the ``job_id`` parameter slot).
    ``SimpleNamespace`` is lighter than ``MagicMock`` here because we want
    missing attributes to raise (so the handler's defensive ``getattr`` paths
    are actually exercised).
    """
    return SimpleNamespace(
        name=name,
        max_retries=max_retries,
        request=SimpleNamespace(retries=retries),
        run=run_fn,
    )


# Stand-in run functions matching the real task signatures verified in
# infrastructure/messaging/*.py. These exist so the signal handler can
# locate ``job_id`` by name via inspect.signature rather than guessing.
def _run_masking_sig(self, policy_id, connection_id, project_id, job_id):  # noqa: D401
    pass


def _run_workflow_sig(self, workflow_id, project_id, job_id):  # noqa: D401
    pass


def _run_discovery_sig(self, connection_id, project_id, job_id):  # noqa: D401
    pass


class TestDlqHandlerGating:
    def test_no_op_when_retries_below_max(self):
        """Mid-retry failures must NOT dead-letter the job; only terminal failures do.

        If we wrote a DLQ row on every intermediate retry, the DLQ would fill
        with spurious rows that the worker is actively recovering from.
        """
        sender = _make_sender(max_retries=2, retries=1)
        job_id = str(uuid.uuid4())

        with patch("app.infrastructure.persistence.database.get_sync_session") as mock_session:
            _handle_task_failure_to_dlq(
                sender=sender,
                task_id="celery-task-id",
                exception=RuntimeError("transient"),
                args=[],
                kwargs={"job_id": job_id},
            )
            # Handler should have bailed before opening a session.
            mock_session.assert_not_called()

    def test_no_op_when_no_job_id_resolvable(self):
        """If we can't find a job_id in args/kwargs, we silently skip."""
        sender = _make_sender(max_retries=2, retries=2)

        with patch("app.infrastructure.persistence.database.get_sync_session") as mock_session:
            _handle_task_failure_to_dlq(
                sender=sender,
                task_id="celery-task-id",
                exception=RuntimeError("boom"),
                args=["not-a-uuid"],
                kwargs={},
            )
            mock_session.assert_not_called()

    def test_no_op_when_sender_missing(self):
        """Defensive guard: missing sender shouldn't explode."""
        # Should not raise; nothing to assert beyond that.
        _handle_task_failure_to_dlq(
            sender=None,
            task_id="x",
            exception=RuntimeError("x"),
            args=[],
            kwargs={},
        )


class TestDlqHandlerInsertion:
    def test_inserts_dlq_row_when_retries_exhausted(self):
        """When ``retries >= max_retries`` and a job_id is present, the handler
        opens a sync session and runs an INSERT ... ON CONFLICT DO NOTHING.
        """
        sender = _make_sender(
            name="app.infrastructure.messaging.masking_tasks.run_masking_task",
            max_retries=2,
            retries=2,
        )
        job_id = str(uuid.uuid4())

        # Build a context-manager mock around the sync Session so we can
        # observe execute() / commit() calls without touching the real DB.
        session_mock = MagicMock()
        ctx_mgr = MagicMock()
        ctx_mgr.__enter__.return_value = session_mock
        ctx_mgr.__exit__.return_value = False

        with patch(
            "app.infrastructure.persistence.database.get_sync_session",
            return_value=ctx_mgr,
        ):
            _handle_task_failure_to_dlq(
                sender=sender,
                task_id="celery-task-id",
                exception=RuntimeError("permanent failure"),
                args=[],
                kwargs={"job_id": job_id, "connection_id": "abc"},
            )

        # Session opened, a statement executed, and a commit issued.
        assert session_mock.execute.called, "expected INSERT to be executed"
        assert session_mock.commit.called, "expected commit after insert"

    def test_finds_job_id_in_positional_args_workflow_signature(self):
        """For tasks that pass ``job_id`` positionally (workflow_tasks-style),
        the handler introspects the task signature to find the right slot.

        ``run_workflow_task(self, workflow_id, project_id, job_id)`` puts
        ``job_id`` at args[2]. The handler must NOT confuse it with
        ``workflow_id`` at args[0] (which would also UUID-validate).
        """
        sender = _make_sender(
            name="app.infrastructure.messaging.workflow_tasks.run_workflow_task",
            max_retries=1,
            retries=1,
            run_fn=_run_workflow_sig,
        )
        workflow_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        session_mock = MagicMock()
        ctx_mgr = MagicMock()
        ctx_mgr.__enter__.return_value = session_mock
        ctx_mgr.__exit__.return_value = False

        captured = {}

        def _capture(stmt):
            # Capture the compiled INSERT params so we can assert the right
            # UUID was used for original_job_id.
            captured["stmt"] = stmt
            return MagicMock()

        session_mock.execute.side_effect = _capture

        with patch(
            "app.infrastructure.persistence.database.get_sync_session",
            return_value=ctx_mgr,
        ):
            _handle_task_failure_to_dlq(
                sender=sender,
                task_id="celery-task-id",
                exception=ValueError("bad input"),
                args=[workflow_id, project_id, job_id],
                kwargs={},
            )

        assert session_mock.execute.called
        assert session_mock.commit.called
        # Verify the INSERT used job_id (args[2]), not workflow_id (args[0]).
        stmt = captured["stmt"]
        # SQLAlchemy Insert.compile().params contains the bound values.
        compiled = stmt.compile()
        bound = compiled.params
        assert str(bound["original_job_id"]) == job_id, (
            f"DLQ wrote wrong original_job_id — expected job_id ({job_id}) "
            f"but got {bound['original_job_id']} (likely workflow_id confusion)"
        )

    def test_masking_signature_picks_job_id_not_policy_id(self):
        """REGRESSION: ``run_masking_task(self, policy_id, connection_id,
        project_id, job_id)`` has job_id at args[3]. A naive implementation
        that reads args[0] would write ``policy_id`` as ``original_job_id``
        — silently corrupting DLQ rows. Verifies signature inspection
        picks the right slot.
        """
        sender = _make_sender(
            name="app.infrastructure.messaging.masking_tasks.run_masking_task",
            max_retries=2,
            retries=2,
            run_fn=_run_masking_sig,
        )
        policy_id = str(uuid.uuid4())
        connection_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        session_mock = MagicMock()
        ctx_mgr = MagicMock()
        ctx_mgr.__enter__.return_value = session_mock
        ctx_mgr.__exit__.return_value = False
        captured = {}

        def _capture(stmt):
            captured["stmt"] = stmt
            return MagicMock()

        session_mock.execute.side_effect = _capture

        with patch(
            "app.infrastructure.persistence.database.get_sync_session",
            return_value=ctx_mgr,
        ):
            _handle_task_failure_to_dlq(
                sender=sender,
                task_id="celery-task-id",
                exception=RuntimeError("permanent failure"),
                args=[policy_id, connection_id, project_id, job_id],
                kwargs={},
            )

        assert session_mock.execute.called
        stmt = captured["stmt"]
        bound = stmt.compile().params
        assert str(bound["original_job_id"]) == job_id, (
            f"DLQ wrote wrong original_job_id — expected job_id ({job_id}) "
            f"but got {bound['original_job_id']} (likely policy_id confusion)"
        )


class TestDlqHandlerResilience:
    def test_swallows_db_exceptions(self):
        """The handler must never let DLQ insertion failure escape — doing so
        would mask the original task exception and potentially crash the
        Celery worker process. This is observability, not correctness.
        """
        sender = _make_sender(max_retries=0, retries=0)
        job_id = str(uuid.uuid4())

        # Make the sync session raise the moment it's entered.
        ctx_mgr = MagicMock()
        ctx_mgr.__enter__.side_effect = RuntimeError("database is down")

        with patch(
            "app.infrastructure.persistence.database.get_sync_session",
            return_value=ctx_mgr,
        ):
            # Should NOT raise.
            _handle_task_failure_to_dlq(
                sender=sender,
                task_id="celery-task-id",
                exception=RuntimeError("permanent failure"),
                args=[],
                kwargs={"job_id": job_id},
            )
