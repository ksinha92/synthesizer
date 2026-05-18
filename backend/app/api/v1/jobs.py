"""Job API endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.job.handlers import CancelJobHandler, GetJobHandler, ListJobsHandler, RetryJobHandler
from app.domain.shared.errors import NotFoundError
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.job_repo import JobRepository

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    progress: int
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class JobDetailResponse(JobResponse):
    """Single-job view used by the Tonic-style details drawer. Carries the
    rich fields the list response intentionally omits to keep listings light:
    domain reference id, who started it, computed duration in seconds, and
    the result summary / checkpoint blobs the worker writes.
    """

    reference_id: str
    created_by: str
    cancelled_at: str | None
    duration_seconds: int | None
    result_summary: dict | None
    checkpoint: dict | None


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total_count: int
    page: int
    page_size: int


@router.get("", response_model=JobListResponse)
async def list_jobs(
    project_id: uuid.UUID,
    page: int = 1, page_size: int = 20,
    job_type: str | None = None, status: str | None = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = JobRepository(session)
    handler = ListJobsHandler(repo)
    jobs, total = await handler.handle(project_id, page, page_size, job_type, status)
    return JobListResponse(
        items=[_job_response(j) for j in jobs],
        total_count=total, page=page, page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    project_id: uuid.UUID, job_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = JobRepository(session)
    handler = GetJobHandler(repo)
    try:
        job = await handler.handle(job_id)
    except NotFoundError:
        raise HTTPException(404, {"error": "not_found", "detail": "Job not found"})
    if job.project_id != project_id:
        raise HTTPException(404, {"error": "not_found", "detail": "Job not found"})
    return _job_detail_response(job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    project_id: uuid.UUID, job_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = JobRepository(session)
    handler = CancelJobHandler(repo)
    try:
        job = await handler.handle(job_id, project_id)
    except NotFoundError:
        raise HTTPException(404, {"error": "not_found", "detail": "Job not found"})
    return _job_response(job)


@router.post("/{job_id}/retry")
async def retry_job(
    project_id: uuid.UUID, job_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = JobRepository(session)
    handler = RetryJobHandler(repo)
    try:
        new_id = await handler.handle(job_id, project_id, uuid.UUID(current_user["id"]))
    except NotFoundError:
        raise HTTPException(404, {"error": "not_found", "detail": "Job not found"})
    except ValueError as e:
        raise HTTPException(400, {"error": "invalid_state", "detail": str(e)})
    return {"job_id": str(new_id), "status": "pending"}


def _safe_job_type(job) -> str:
    """Tolerate ``job.job_type`` being either a ``JobType`` enum or a raw
    string the repo could not coerce to the enum.

    Newer worker code can write job rows whose ``job_type`` value is not yet
    present in the ``JobType`` enum (mid-migration, plugin-provided types,
    legacy rows). We must not 500 the jobs API on those — return "unknown"
    instead so the UI can render the row.
    """
    try:
        if hasattr(job.job_type, "value"):
            return job.job_type.value
        return str(job.job_type)
    except (AttributeError, ValueError):
        return "unknown"


def _job_response(job) -> JobResponse:
    return JobResponse(
        id=str(job.id), job_type=_safe_job_type(job), status=job.status.value,
        progress=job.progress, error_message=job.error_message,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        created_at=job.created_at.isoformat() if job.created_at else "",
    )


def _job_detail_response(job) -> JobDetailResponse:
    duration = None
    if job.started_at and job.completed_at:
        duration = int((job.completed_at - job.started_at).total_seconds())
    return JobDetailResponse(
        id=str(job.id), job_type=_safe_job_type(job), status=job.status.value,
        progress=job.progress, error_message=job.error_message,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        created_at=job.created_at.isoformat() if job.created_at else "",
        reference_id=str(job.reference_id),
        created_by=str(job.created_by),
        cancelled_at=job.cancelled_at.isoformat() if job.cancelled_at else None,
        duration_seconds=duration,
        result_summary=job.result_summary,
        checkpoint=job.checkpoint,
    )
