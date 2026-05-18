"""Compliance API endpoints."""

from __future__ import annotations

import json
import uuid

import structlog
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.job import JobModel
from app.infrastructure.persistence.sqlalchemy.compliance_repo import ComplianceRepository
from app.infrastructure.storage.base import StorageBackend

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/compliance",
    tags=["compliance"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


class GenerateRequest(BaseModel):
    regulation: str  # hipaa | gdpr | ccpa


class ReportResponse(BaseModel):
    id: str
    report_type: str
    generated_at: str
    summary: dict
    storage_path: str
    # Phase 57: surfaces reports that were generated before the empty-payload
    # bug was fixed. UI uses this to badge them as "incomplete".
    legacy: bool = False


class AcceptedResponse(BaseModel):
    """202 envelope returned when the report is queued for background work."""

    job_id: str
    status: str


@router.post("/reports", response_model=AcceptedResponse, status_code=202)
async def generate_report(
    project_id: uuid.UUID, body: GenerateRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Enqueue compliance report generation.

    Phase 57 F2: previously this ran the full handler in-thread, which
    blocked the request for the entire PDF generation cycle and made
    HIPAA/GDPR/CCPA reports vulnerable to gateway timeouts on large
    projects. The handler now lives on the Celery worker pool; this
    endpoint persists a JobModel row, hands the work to the task, and
    returns a 202 + Location header so callers can poll /jobs/{id} or
    listen on the SSE event stream.
    """
    if body.regulation not in ("hipaa", "gdpr", "ccpa"):
        raise HTTPException(400, {"error": "invalid_regulation", "detail": "Must be hipaa, gdpr, or ccpa"})

    try:
        user_uuid = uuid.UUID(current_user["id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, {"error": "invalid_user", "detail": "Missing or malformed user id"})

    job = JobModel(
        project_id=project_id,
        job_type="compliance",
        reference_id=project_id,
        status="pending",
        progress=0,
        created_by=user_uuid,
    )
    session.add(job)
    await session.flush()
    job_id = job.id
    # Commit so the Celery worker picks up the row when it lands. Without
    # this, the .delay() below can race the request-scoped session's
    # implicit commit and the task wakes up to find no JobModel row.
    await session.commit()

    # Import locally to avoid pulling Celery at module-import time during
    # routes that don't need it (keeps the FastAPI startup graph small).
    from app.infrastructure.messaging.compliance_tasks import run_report_generation

    run_report_generation.delay(
        str(job_id),
        str(project_id),
        body.regulation,
        str(user_uuid),
    )

    body_payload = {"job_id": str(job_id), "status": "pending"}
    return Response(
        status_code=202,
        content=json.dumps(body_payload),
        media_type="application/json",
        headers={"Location": f"/api/v1/projects/{project_id}/jobs/{job_id}"},
    )


@router.get("/reports")
async def list_reports(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = ComplianceRepository(session)
    reports = await repo.find_by_project_id(project_id)
    return {"reports": [
        ReportResponse(
            id=str(r.id),
            report_type=r.report_type,
            generated_at=r.generated_at.isoformat(),
            summary=r.summary,
            storage_path=r.storage_path,
            legacy=getattr(r, "legacy", False),
        ).model_dump()
        for r in reports
    ]}


@router.get("/reports/{report_id}/download")
@inject
async def download_report(
    project_id: uuid.UUID, report_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
    storage: StorageBackend = Depends(Provide["storage_backend"]),
):
    """Download compliance report PDF. Requires auth + project ownership."""
    repo = ComplianceRepository(session)
    report = await repo.get(report_id)
    if not report or report.project_id != project_id:
        raise HTTPException(404, {"error": "not_found"})

    try:
        pdf_bytes = await storage.load(report.storage_path)
    except FileNotFoundError:
        raise HTTPException(404, {"error": "file_not_found", "detail": "Report PDF not found in storage"})

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={report.report_type}_report_{report_id}.pdf"},
    )
