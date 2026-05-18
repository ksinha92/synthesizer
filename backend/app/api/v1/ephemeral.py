"""Ephemeral environments API (T3.1, Tonic 11.25.00 / 11.35.01 / 11.35.09).

Phase 61 F18 wired the actual data-copy controller in:
``POST /ephemeral`` now dispatches a Celery task (``run_ephemeral_provision_task``)
that spawns a sidecar Docker container, copies source data into it, and
flips the row to ``ready`` with a ``connection_string`` the UI surfaces.

The lazy TTL sweep that used to run inside GET handlers is gone —
``run_ephemeral_expire_sweep_task`` (celery-beat) owns it now, which
means GETs are pure reads and the sweep can stop containers without
racing the read path.

Lifecycle: ``pending → provisioning → ready → expired | revoked | failed``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.connection import ConnectionModel
from app.infrastructure.persistence.models.ephemeral import EphemeralEnvironmentModel
from app.infrastructure.persistence.models.job import JobModel
from app.infrastructure.persistence.models.project import ProjectModel

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/ephemeral",
    tags=["ephemeral"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


ALLOWED_STATUSES = {"pending", "provisioning", "ready", "expired", "revoked", "failed"}
MAX_TTL_DAYS = 30
DEFAULT_TTL_DAYS = 7
MAX_TTL_HOURS = MAX_TTL_DAYS * 24


class EphemeralCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    destination_connection_id: uuid.UUID | None = None
    source_job_id: uuid.UUID | None = None
    schema_name: str | None = Field(None, max_length=255)
    ttl_days: int = Field(default=DEFAULT_TTL_DAYS, ge=1, le=MAX_TTL_DAYS)


class EphemeralExtend(BaseModel):
    """Body for ``POST /ephemeral/{id}/extend``.

    ``additional_hours`` defaults to 24 (matching the "give me another
    day" UI affordance). Validation bounds keep the value sane; the
    30-day cap on *total* TTL is enforced in the handler because it
    depends on the row's current ``expires_at``.
    """

    additional_hours: int = Field(default=24, ge=1, le=MAX_TTL_HOURS)


class EphemeralResponse(BaseModel):
    id: str
    project_id: str
    name: str
    source_job_id: str | None
    destination_connection_id: str | None
    schema_name: str | None
    status: str
    expires_at: str
    created_by: str
    created_at: str
    updated_at: str
    # Computed: how many seconds until expiry. Negative means already
    # expired even if the sweep hasn't flipped the row yet.
    seconds_remaining: int
    # Controller-owned fields. Null until the row reaches ``ready``.
    connection_string: str | None
    host_port: int | None
    container_id: str | None


class EphemeralListResponse(BaseModel):
    items: list[EphemeralResponse]
    total_count: int


class EphemeralCreateResponse(BaseModel):
    """202 response from POST /ephemeral — the controller is async."""

    env_id: str
    job_id: str
    status: str


# ── Helpers ────────────────────────────────────────────────────────────────


def _to_response(env: EphemeralEnvironmentModel) -> EphemeralResponse:
    now = datetime.now(timezone.utc)
    delta = (env.expires_at - now).total_seconds() if env.expires_at else 0
    return EphemeralResponse(
        id=str(env.id),
        project_id=str(env.project_id),
        name=env.name,
        source_job_id=str(env.source_job_id) if env.source_job_id else None,
        destination_connection_id=(
            str(env.destination_connection_id)
            if env.destination_connection_id
            else None
        ),
        schema_name=env.schema_name,
        status=env.status,
        expires_at=env.expires_at.isoformat() if env.expires_at else "",
        created_by=str(env.created_by),
        created_at=env.created_at.isoformat() if env.created_at else "",
        updated_at=env.updated_at.isoformat() if env.updated_at else "",
        seconds_remaining=int(delta),
        connection_string=env.connection_string,
        host_port=env.host_port,
        container_id=env.container_id,
    )


async def _assert_project_exists(session: AsyncSession, project_id: uuid.UUID) -> None:
    result = await session.execute(
        select(ProjectModel.id).where(ProjectModel.id == project_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Project not found"})


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("", response_model=EphemeralListResponse)
async def list_ephemeral(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """List envs without write side-effects.

    The lazy ``_maybe_flip_expired`` write that used to run here is gone;
    the celery-beat sweep task owns TTL flips. The UI can still display
    ``seconds_remaining < 0`` for rows the sweep hasn't picked up yet —
    in practice the sweep cadence (≤ 5 min) makes that window invisible.
    """
    await _assert_project_exists(session, project_id)

    result = await session.execute(
        select(EphemeralEnvironmentModel)
        .where(EphemeralEnvironmentModel.project_id == project_id)
        .order_by(EphemeralEnvironmentModel.created_at.desc())
    )
    envs = result.scalars().all()
    return EphemeralListResponse(
        items=[_to_response(e) for e in envs],
        total_count=len(envs),
    )


@router.post("", response_model=EphemeralCreateResponse, status_code=202)
async def create_ephemeral(
    project_id: uuid.UUID,
    body: EphemeralCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Kick off async provisioning of an ephemeral environment.

    Returns 202 immediately with ``{env_id, job_id, status: "pending"}``.
    The actual container spawn happens in ``run_ephemeral_provision_task``;
    poll GET to watch the row flip ``pending → provisioning → ready``.
    """
    await _assert_project_exists(session, project_id)

    if body.destination_connection_id is not None:
        result = await session.execute(
            select(ConnectionModel.project_id).where(
                ConnectionModel.id == body.destination_connection_id
            )
        )
        owner_project = result.scalar_one_or_none()
        if owner_project is None or owner_project != project_id:
            raise HTTPException(
                400,
                {
                    "error": "invalid_destination",
                    "detail": "destination_connection_id must belong to this project",
                },
            )

    if body.source_job_id is not None:
        result = await session.execute(
            select(JobModel.project_id).where(JobModel.id == body.source_job_id)
        )
        owner_project = result.scalar_one_or_none()
        if owner_project is None or owner_project != project_id:
            raise HTTPException(
                400,
                {
                    "error": "invalid_source_job",
                    "detail": "source_job_id must belong to this project",
                },
            )

    expires_at = datetime.now(timezone.utc) + timedelta(days=body.ttl_days)
    env_id = uuid.uuid4()
    job_id = uuid.uuid4()

    env = EphemeralEnvironmentModel(
        id=env_id,
        project_id=project_id,
        name=body.name,
        source_job_id=body.source_job_id,
        destination_connection_id=body.destination_connection_id,
        schema_name=body.schema_name or f"ephemeral_{uuid.uuid4().hex[:8]}",
        status="pending",
        expires_at=expires_at,
        created_by=uuid.UUID(current_user["id"]),
    )
    job = JobModel(
        id=job_id,
        project_id=project_id,
        # Must match JobType.EPHEMERAL = "ephemeral"; the previous
        # "ephemeral_provision" couldn't be hydrated by JobRepository
        # and crashed every later jobs-API read for ephemeral jobs.
        job_type="ephemeral",
        reference_id=env_id,
        status="pending",
        created_by=uuid.UUID(current_user["id"]),
    )
    session.add(env)
    session.add(job)
    # Commit (not just flush) BEFORE enqueueing so the worker can find both
    # rows. On a fast broker, .delay() can dispatch before the request-scoped
    # session.commit() at teardown, racing the worker against pending rows.
    await session.commit()

    # Dispatch the Celery task. Import here so the API module stays
    # importable even when celery isn't installed (e.g. typecheck-only
    # environments). ``.delay`` is safe to call from an async handler —
    # it's a synchronous enqueue + immediate return.
    try:
        from app.infrastructure.messaging.ephemeral_tasks import (
            run_ephemeral_provision_task,
        )

        run_ephemeral_provision_task.delay(
            str(env_id), str(project_id), str(job_id)
        )
    except Exception as e:  # noqa: BLE001
        # If broker is unreachable, surface the failure rather than
        # leave the row pending forever -- the sweep will eventually
        # flip it to ``failed``, but the user deserves a real error now.
        await logger.aerror(
            "ephemeral_dispatch_failed",
            env_id=str(env_id),
            error=str(e),
        )
        raise HTTPException(
            503,
            {
                "error": "dispatch_failed",
                "detail": "Could not dispatch ephemeral provisioning task",
            },
        ) from e

    await logger.ainfo(
        "ephemeral_created",
        project_id=str(project_id),
        ephemeral_id=str(env_id),
        job_id=str(job_id),
        ttl_days=body.ttl_days,
        user_id=current_user["id"],
    )

    return EphemeralCreateResponse(
        env_id=str(env_id), job_id=str(job_id), status="pending"
    )


@router.post(
    "/{ephemeral_id}/extend", response_model=EphemeralResponse, status_code=200
)
async def extend_ephemeral(
    project_id: uuid.UUID,
    ephemeral_id: uuid.UUID,
    body: EphemeralExtend,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Push the expiry out by ``additional_hours``.

    Total TTL (from ``created_at`` to the new ``expires_at``) is capped
    at 30 days to keep ephemeral envs ephemeral. Calling extend on a
    row that's already ``expired`` or ``revoked`` returns 400 — extend
    only makes sense while the env is alive.
    """
    result = await session.execute(
        select(EphemeralEnvironmentModel).where(
            EphemeralEnvironmentModel.id == ephemeral_id,
            EphemeralEnvironmentModel.project_id == project_id,
        )
    )
    env = result.scalar_one_or_none()
    if env is None:
        raise HTTPException(
            404, {"error": "not_found", "detail": "Ephemeral environment not found"}
        )
    if env.status in {"expired", "revoked", "failed"}:
        raise HTTPException(
            400,
            {
                "error": "invalid_state",
                "detail": f"Cannot extend env in status '{env.status}'",
            },
        )

    new_expires = env.expires_at + timedelta(hours=body.additional_hours)
    # Cap total TTL at 30 days from creation. We measure from
    # ``created_at`` rather than ``now`` so repeated extends can't drift
    # the cap forward indefinitely.
    cap = env.created_at + timedelta(days=MAX_TTL_DAYS)
    if new_expires > cap:
        raise HTTPException(
            400,
            {
                "error": "ttl_cap_exceeded",
                "detail": (
                    f"Total TTL cannot exceed {MAX_TTL_DAYS} days from creation"
                ),
            },
        )

    env.expires_at = new_expires
    await session.flush()
    await logger.ainfo(
        "ephemeral_extended",
        project_id=str(project_id),
        ephemeral_id=str(ephemeral_id),
        additional_hours=body.additional_hours,
        user_id=current_user["id"],
    )
    return _to_response(env)


@router.delete("/{ephemeral_id}", status_code=204)
async def revoke_ephemeral(
    project_id: uuid.UUID,
    ephemeral_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Revoke an ephemeral environment.

    Flips status to ``revoked`` instead of hard-deleting so the audit log
    stays intact. If a container is attached, we stop+remove it inline
    so the host doesn't keep paying for the DB process. Idempotent —
    revoking an already-revoked row returns 204 without re-tearing-down.
    """
    result = await session.execute(
        select(EphemeralEnvironmentModel).where(
            EphemeralEnvironmentModel.id == ephemeral_id,
            EphemeralEnvironmentModel.project_id == project_id,
        )
    )
    env = result.scalar_one_or_none()
    if env is None:
        raise HTTPException(
            404, {"error": "not_found", "detail": "Ephemeral environment not found"}
        )

    if env.status == "revoked":
        return  # already revoked, no work to do

    # Stop the container BEFORE flipping status -- if teardown fails we
    # still want the row to read ``revoked`` so the user can retry, but
    # we log the failure so an operator can clean up manually.
    if env.container_id:
        try:
            from app.infrastructure.ephemeral.docker_provisioner import (
                DockerProvisioner,
            )

            await DockerProvisioner().stop_and_remove(env.container_id)
        except Exception as e:  # noqa: BLE001
            await logger.awarning(
                "ephemeral_revoke_teardown_failed",
                ephemeral_id=str(ephemeral_id),
                container_id=env.container_id,
                error=str(e),
            )

    env.status = "revoked"
    env.revoked_at = datetime.now(timezone.utc)
    await session.flush()
    await logger.ainfo(
        "ephemeral_revoked",
        project_id=str(project_id),
        ephemeral_id=str(ephemeral_id),
        user_id=current_user["id"],
    )
