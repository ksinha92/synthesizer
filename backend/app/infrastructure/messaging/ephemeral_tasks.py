"""Ephemeral environment Celery tasks (Phase 61 F18).

Two tasks live here:

* ``run_ephemeral_provision_task`` -- one-shot per-env-id job that spins
  the container, copies the data, and flips the env row to ``ready``.
  Mirrors the pattern in ``discovery_tasks`` / ``masking_tasks`` -- DB
  state transitions wrap the actual work and live alongside webhook
  fire-and-forget calls.
* ``run_ephemeral_expire_sweep_task`` -- recurring beat task that finds
  rows past ``expires_at`` (or stuck pending > 1h) and reaps the
  associated containers. Replaces the lazy ``_maybe_flip_expired`` write
  side-effect that used to run inside GET handlers, which kept the UI's
  freshness story alive at the cost of writes on every read.

The ephemeral domain is intentionally a stub (no service object, no
entity beyond the ORM row) -- the orchestration logic lives here in the
task body because the workflow is fundamentally a queue+DB+container
choreography, not domain logic.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update

from app.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger()


# An env that has been "pending" longer than this is presumed stuck -- the
# worker that picked it up either died or never started. The sweep task
# flips these to ``failed`` so the UI doesn't pretend they're still in
# flight forever.
STUCK_PENDING_THRESHOLD = timedelta(hours=1)


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    acks_late=True,
)
def run_ephemeral_provision_task(
    self, env_id: str, project_id: str, job_id: str
) -> None:
    """Provision an ephemeral container, copy data, mark the env ready.

    Retries once (120s) on transient failure -- typical failure modes
    (docker daemon hiccup, source connector flapping) recover on a single
    retry. After two consecutive failures we let it fail loudly so it
    lands in the DLQ rather than thrashing.
    """
    asyncio.run(_provision_async(self, env_id, project_id, job_id))


@celery_app.task(bind=True, acks_late=True)
def run_ephemeral_expire_sweep_task(self) -> None:  # noqa: ARG002
    """Sweep ready→expired and stuck-pending→failed rows.

    Designed for celery-beat at a 1- to 5-minute cadence. Idempotent --
    re-running it never reverses a flip. Containers are stopped+removed
    as part of the expired transition; teardown errors are swallowed so a
    single bad container doesn't block the rest of the sweep batch.
    """
    asyncio.run(_sweep_async())


async def _provision_async(
    task, env_id: str, project_id: str, job_id: str
) -> None:
    """Async workhorse for :func:`run_ephemeral_provision_task`.

    Steps:
      1. Load env + job. Stamp ``celery_task_id`` so cancel-by-id works.
      2. Flip env→``provisioning``, job→``running`` (commit).
      3. Spin the container, wait for ready.
      4. If a source connection is attached, copy the data.
      5. Flip env→``ready`` with container_id / host_port / conn_string.
      6. Flip job→``completed`` + emit ``ephemeral.ready`` webhook.

    On exception: flip env→``failed`` and job→``failed``, teardown any
    container that did get spawned, then re-raise so Celery autoretry +
    DLQ paths see the failure.
    """
    from app.infrastructure.ephemeral.data_copy import copy_data
    from app.infrastructure.ephemeral.docker_provisioner import DockerProvisioner
    from app.infrastructure.messaging.celery_app import fire_webhooks
    from app.infrastructure.messaging.progress_pubsub import publish_progress
    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.connection import ConnectionModel
    from app.infrastructure.persistence.models.ephemeral import (
        EphemeralEnvironmentModel,
    )
    from app.infrastructure.persistence.models.job import JobModel
    from app.infrastructure.persistence.sqlalchemy.connection_repo import (
        _decrypt_credentials,
    )

    env_uuid = uuid.UUID(env_id)
    job_uuid = uuid.UUID(job_id)

    provisioner = DockerProvisioner()
    container_id: str | None = None

    async with async_session_factory() as session:
        try:
            env = await session.get(EphemeralEnvironmentModel, env_uuid)
            if env is None:
                raise ValueError(f"ephemeral env {env_id} not found")
            job = await session.get(JobModel, job_uuid)
            if job is None:
                raise ValueError(f"job {job_id} not found")

            # F9: stamp celery_task_id so cancel-by-Celery-id works.
            if not job.celery_task_id:
                job.celery_task_id = task.request.id

            env.status = "provisioning"
            env.provisioning_started_at = datetime.now(timezone.utc)
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await session.commit()
            publish_progress(
                str(job_uuid),
                {"status": "running", "progress": 10, "result_summary": None},
            )

            # Random root creds -- ephemeral, never reused, never logged.
            root_user = "dataw"
            root_password = secrets.token_urlsafe(24)
            # Engine inferred from the destination connection if present,
            # otherwise default to postgresql which is the safest no-op
            # for downstream tooling.
            engine = "postgresql"
            if env.destination_connection_id is not None:
                dest = await session.get(
                    ConnectionModel, env.destination_connection_id
                )
                if dest and dest.connector_type in {"postgresql", "mysql", "mongodb"}:
                    engine = dest.connector_type

            handle = await provisioner.provision(
                env_id=str(env.id),
                engine=engine,
                db_name=env.schema_name or "ephemeral",
                root_user=root_user,
                root_password=root_password,
            )
            container_id = handle.container_id

            ready = await provisioner.wait_for_ready(
                container_id=handle.container_id,
                engine=engine,
                host_port=handle.host_port,
                timeout=60,
            )
            if not ready:
                raise RuntimeError("container did not become ready within timeout")

            publish_progress(
                str(job_uuid),
                {"status": "running", "progress": 50, "result_summary": None},
            )

            # Copy data if a source job exists -- the source job's
            # connection_id is reachable via the JobModel.reference_id
            # (job_type=='discovery' / 'masking' both point to a
            # connection). We resolve source connector from
            # ``env.source_job_id`` -> JobModel.reference_id -> ConnectionModel.
            copy_summary: dict | None = None
            target_dsn = _build_target_dsn(
                engine=engine,
                host_port=handle.host_port,
                db_name=env.schema_name or "ephemeral",
                user=root_user,
                password=root_password,
            )
            if env.source_job_id is not None:
                source_job = await session.get(JobModel, env.source_job_id)
                if source_job is not None:
                    src_conn = await session.get(
                        ConnectionModel, source_job.reference_id
                    )
                    if src_conn is not None:
                        creds = _decrypt_credentials(src_conn.credentials or {})
                        source_conn_dict = {
                            "connector_type": src_conn.connector_type,
                            "host": src_conn.host,
                            "port": src_conn.port,
                            "database_name": src_conn.database_name,
                            "username": creds.get("username", ""),
                            "password": creds.get("password", ""),
                            "extra_params": src_conn.extra_params or {},
                        }
                        # Masking policy is currently not threaded onto
                        # the ephemeral row (no column yet) -- unmasked
                        # copy is the v0.9 contract.
                        copy_summary = await copy_data(
                            source_conn=source_conn_dict,
                            target_dsn=target_dsn,
                            masking_policy_id=None,
                            session=session,
                        )

            env.status = "ready"
            env.container_id = handle.container_id
            env.host_port = handle.host_port
            env.connection_string = target_dsn
            env.ready_at = datetime.now(timezone.utc)

            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            job.result_summary = {
                "env_id": env_id,
                "container_id": handle.container_id,
                "host_port": handle.host_port,
                "engine": engine,
                "copy_summary": copy_summary,
            }
            await session.commit()

            publish_progress(
                str(job_uuid),
                {
                    "status": "completed",
                    "progress": 100,
                    "result_summary": job.result_summary,
                },
            )
            await fire_webhooks(
                project_id,
                "ephemeral.ready",
                {
                    "env_id": env_id,
                    "container_id": handle.container_id,
                    "host_port": handle.host_port,
                    "engine": engine,
                },
            )

            await logger.ainfo(
                "ephemeral_provision_completed",
                env_id=env_id,
                container_id=handle.container_id,
            )

        except Exception as exc:
            await session.rollback()
            # Teardown any container that did get spawned -- otherwise
            # the failure leaves a zombie running on the host.
            if container_id:
                try:
                    await provisioner.stop_and_remove(container_id)
                except Exception:  # noqa: BLE001
                    pass

            async with async_session_factory() as err_session:
                await err_session.execute(
                    update(EphemeralEnvironmentModel)
                    .where(EphemeralEnvironmentModel.id == env_uuid)
                    .values(status="failed")
                )
                await err_session.execute(
                    update(JobModel)
                    .where(JobModel.id == job_uuid)
                    .values(
                        status="failed",
                        error_message=str(exc)[:1000],
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await err_session.commit()
            publish_progress(
                str(job_uuid),
                {"status": "failed", "progress": 0, "result_summary": None},
            )
            from app.infrastructure.messaging.celery_app import fire_webhooks as _fw

            await _fw(
                project_id,
                "ephemeral.failed",
                {"env_id": env_id, "error": str(exc)[:500]},
            )
            await logger.aerror(
                "ephemeral_provision_failed",
                env_id=env_id,
                error=str(exc),
            )
            raise


async def _sweep_async() -> None:
    """Find ``ready`` rows past TTL + ``pending`` rows stuck > 1h.

    Two passes, one query each:

    1. ``ready`` past ``expires_at`` -> stop container, mark ``expired``.
    2. ``pending``/``provisioning`` older than ``STUCK_PENDING_THRESHOLD``
       -> mark ``failed`` (no container to stop -- they never made it
       that far, or the worker that spawned them died and we'll never
       know).
    """
    from app.infrastructure.ephemeral.docker_provisioner import DockerProvisioner
    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.ephemeral import (
        EphemeralEnvironmentModel,
    )

    provisioner = DockerProvisioner()
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        # Pass 1: TTL-expired ready rows.
        result = await session.execute(
            select(EphemeralEnvironmentModel).where(
                EphemeralEnvironmentModel.status == "ready",
                EphemeralEnvironmentModel.expires_at < now,
            )
        )
        for env in result.scalars().all():
            if env.container_id:
                try:
                    await provisioner.stop_and_remove(env.container_id)
                except Exception as e:  # noqa: BLE001
                    await logger.awarning(
                        "ephemeral_sweep_teardown_failed",
                        env_id=str(env.id),
                        error=str(e),
                    )
            env.status = "expired"
            env.revoked_at = now
        await session.commit()

        # Pass 2: stuck pending / provisioning rows.
        stuck_cutoff = now - STUCK_PENDING_THRESHOLD
        await session.execute(
            update(EphemeralEnvironmentModel)
            .where(
                EphemeralEnvironmentModel.status.in_(["pending", "provisioning"]),
                EphemeralEnvironmentModel.created_at < stuck_cutoff,
            )
            .values(status="failed")
        )
        await session.commit()

        await logger.ainfo("ephemeral_sweep_done")


def _build_target_dsn(
    engine: str, host_port: int, db_name: str, user: str, password: str
) -> str:
    """Build a SQLAlchemy-compatible DSN for the spawned container.

    We connect from the worker host, so the DB hostname is whatever the
    worker reaches Docker through. ``host.docker.internal`` works inside
    Docker Desktop; outside it (Linux runner without DESKTOP), the env
    var ``EPHEMERAL_DOCKER_HOST`` can override. Default is the loopback
    so unit tests and dev installs work out of the box.
    """
    import os

    host = os.environ.get("EPHEMERAL_DOCKER_HOST", "127.0.0.1")
    if engine == "postgresql":
        return f"postgresql+asyncpg://{user}:{password}@{host}:{host_port}/{db_name}"
    if engine == "mysql":
        return f"mysql+aiomysql://{user}:{password}@{host}:{host_port}/{db_name}"
    # MongoDB -- SQLAlchemy doesn't drive it, but we still surface a URL
    # the user can paste into a client.
    return f"mongodb://{user}:{password}@{host}:{host_port}/{db_name}"
