"""Unit tests for ``_provision_async`` (Phase 61 F18).

We exercise the Celery task's async workhorse directly with a fabricated
session + a stubbed ``DockerProvisioner``. Two paths:

* Happy path: env flips ``pending`` -> ``provisioning`` -> ``ready``;
  job flips to ``completed``; webhook fires with ``ephemeral.ready``.
* Failure path: ``provisioner.provision`` raises -> env + job both
  flip to ``failed`` and the exception re-raises so Celery's autoretry
  / DLQ pipeline sees it.

The session is two-rows-deep (one env, one job) -- ``session.get`` is
the read path the task uses for both, so we configure a ``side_effect``
that returns env first, job second.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
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


def _make_env() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        status="pending",
        schema_name="ephemeral_test",
        source_job_id=None,
        destination_connection_id=None,
        container_id=None,
        host_port=None,
        connection_string=None,
        ready_at=None,
        revoked_at=None,
        provisioning_started_at=None,
    )


def _make_job() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        celery_task_id=None,
        status="pending",
        progress=0,
        started_at=None,
        completed_at=None,
        result_summary=None,
        error_message=None,
    )


def _build_session(env, job) -> MagicMock:
    session = MagicMock()
    # session.get is called twice: first for the env, then for the job.
    session.get = AsyncMock(side_effect=[env, job])
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def test_provision_happy_path_marks_env_ready_and_job_completed():
    """Successful provision: env ends ``ready``, job ends ``completed``."""
    from app.infrastructure.messaging import ephemeral_tasks

    env = _make_env()
    job = _make_job()
    session = _build_session(env, job)

    fake_handle = SimpleNamespace(
        container_id="cont-abc-123",
        host_port=40123,
        root_user="dataw",
        root_password="pw",
        engine="postgresql",
    )

    fake_provisioner_cls = MagicMock()
    instance = MagicMock()
    instance.provision = AsyncMock(return_value=fake_handle)
    instance.wait_for_ready = AsyncMock(return_value=True)
    instance.stop_and_remove = AsyncMock()
    fake_provisioner_cls.return_value = instance

    def _factory():
        return _AsyncCM(session)

    task = SimpleNamespace(request=SimpleNamespace(id="celery-task-id-xyz", retries=0))

    with patch(
        "app.infrastructure.persistence.database.async_session_factory",
        _factory,
    ), patch(
        "app.infrastructure.ephemeral.docker_provisioner.DockerProvisioner",
        fake_provisioner_cls,
    ), patch(
        "app.infrastructure.messaging.celery_app.fire_webhooks",
        new=AsyncMock(),
    ) as fire_mock, patch(
        "app.infrastructure.messaging.progress_pubsub.publish_progress",
        new=MagicMock(return_value=True),
    ):
        asyncio.run(
            ephemeral_tasks._provision_async(
                task,
                str(env.id),
                str(uuid.uuid4()),
                str(job.id),
            )
        )

    # Env ended in ``ready`` with container metadata stamped.
    assert env.status == "ready"
    assert env.container_id == "cont-abc-123"
    assert env.host_port == 40123
    assert env.connection_string is not None
    assert env.ready_at is not None

    # Job ended in ``completed`` with a result summary.
    assert job.status == "completed"
    assert job.progress == 100
    assert job.celery_task_id == "celery-task-id-xyz"
    assert job.result_summary["container_id"] == "cont-abc-123"

    # Webhook fired with the success event.
    fire_mock.assert_awaited()
    args, _ = fire_mock.call_args
    assert "ephemeral.ready" in args


def test_provision_failure_flips_env_and_job_to_failed_and_reraises():
    """When ``provision`` raises, env+job must end in ``failed`` and the
    exception must propagate so Celery's retry layer sees it."""
    import pytest

    from app.infrastructure.messaging import ephemeral_tasks

    env = _make_env()
    job = _make_job()
    session = _build_session(env, job)

    # Separate error-path session for the explicit ``async with`` block
    # that flips the rows to failed.
    err_session = MagicMock()
    err_session.execute = AsyncMock()
    err_session.commit = AsyncMock()

    fake_provisioner_cls = MagicMock()
    instance = MagicMock()
    instance.provision = AsyncMock(side_effect=RuntimeError("docker down"))
    instance.wait_for_ready = AsyncMock(return_value=True)
    instance.stop_and_remove = AsyncMock()
    fake_provisioner_cls.return_value = instance

    factory_calls = {"n": 0}

    def _factory():
        # First call -> main session, subsequent -> error session.
        factory_calls["n"] += 1
        return _AsyncCM(session if factory_calls["n"] == 1 else err_session)

    task = SimpleNamespace(request=SimpleNamespace(id="celery-task", retries=0))

    with patch(
        "app.infrastructure.persistence.database.async_session_factory",
        _factory,
    ), patch(
        "app.infrastructure.ephemeral.docker_provisioner.DockerProvisioner",
        fake_provisioner_cls,
    ), patch(
        "app.infrastructure.messaging.celery_app.fire_webhooks",
        new=AsyncMock(),
    ), patch(
        "app.infrastructure.messaging.progress_pubsub.publish_progress",
        new=MagicMock(return_value=True),
    ):
        with pytest.raises(RuntimeError, match="docker down"):
            asyncio.run(
                ephemeral_tasks._provision_async(
                    task,
                    str(env.id),
                    str(uuid.uuid4()),
                    str(job.id),
                )
            )

    # The error-path session must have issued two updates -- one to flip
    # env to failed, one to flip job to failed.
    assert err_session.execute.await_count == 2
    assert err_session.commit.await_count == 1


def test_provision_wait_for_ready_timeout_marks_failed():
    """If ``wait_for_ready`` returns False, the task must treat it as
    failure -- env+job go to ``failed`` and the spawned container is
    torn down."""
    import pytest

    from app.infrastructure.messaging import ephemeral_tasks

    env = _make_env()
    job = _make_job()
    session = _build_session(env, job)

    err_session = MagicMock()
    err_session.execute = AsyncMock()
    err_session.commit = AsyncMock()

    fake_handle = SimpleNamespace(
        container_id="cont-doomed",
        host_port=40000,
        root_user="u",
        root_password="p",
        engine="postgresql",
    )

    instance = MagicMock()
    instance.provision = AsyncMock(return_value=fake_handle)
    instance.wait_for_ready = AsyncMock(return_value=False)
    instance.stop_and_remove = AsyncMock()
    fake_provisioner_cls = MagicMock(return_value=instance)

    factory_calls = {"n": 0}

    def _factory():
        factory_calls["n"] += 1
        return _AsyncCM(session if factory_calls["n"] == 1 else err_session)

    task = SimpleNamespace(request=SimpleNamespace(id="t", retries=0))

    with patch(
        "app.infrastructure.persistence.database.async_session_factory",
        _factory,
    ), patch(
        "app.infrastructure.ephemeral.docker_provisioner.DockerProvisioner",
        fake_provisioner_cls,
    ), patch(
        "app.infrastructure.messaging.celery_app.fire_webhooks",
        new=AsyncMock(),
    ), patch(
        "app.infrastructure.messaging.progress_pubsub.publish_progress",
        new=MagicMock(return_value=True),
    ):
        with pytest.raises(RuntimeError, match="container did not become ready"):
            asyncio.run(
                ephemeral_tasks._provision_async(
                    task,
                    str(env.id),
                    str(uuid.uuid4()),
                    str(job.id),
                )
            )

    # The doomed container was torn down on the failure path.
    instance.stop_and_remove.assert_awaited_with("cont-doomed")
