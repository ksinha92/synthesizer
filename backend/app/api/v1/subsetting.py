"""Subsetting API endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.subsetting.commands import *
from app.application.subsetting.handlers import *
from app.domain.shared.errors import NotFoundError
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.subsetting_repo import SubsettingRepository

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/subset",
    tags=["subsetting"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


ALLOWED_OUTPUT_MODES = {"same_database", "different_connection", "download_zip", "s3"}


class SubsetConfigCreate(BaseModel):
    name: str
    source_connection_id: str
    target_percentage: float | None = None
    target_row_count: int | None = None
    root_tables: list[dict] = Field(default_factory=list)
    traversal_strategy: str = "upstream"
    output_mode: str = "same_database"


class AnalyzeRequest(BaseModel):
    config_id: str


class ExecuteRequest(BaseModel):
    config_id: str


class OutputModeUpdate(BaseModel):
    output_mode: str


@router.patch("/configs/{config_id}/output-mode")
async def update_subset_output_mode(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    body: OutputModeUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Update only the output_mode of a subset config."""
    if body.output_mode not in ALLOWED_OUTPUT_MODES:
        raise HTTPException(
            400,
            {
                "error": "invalid_output_mode",
                "detail": f"output_mode must be one of {sorted(ALLOWED_OUTPUT_MODES)}",
            },
        )
    from sqlalchemy import select as _select
    from app.infrastructure.persistence.models.subsetting import SubsetConfigModel

    res = await session.execute(
        _select(SubsetConfigModel).where(
            SubsetConfigModel.id == config_id,
            SubsetConfigModel.project_id == project_id,
        )
    )
    model = res.scalar_one_or_none()
    if model is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Config not found"})

    model.output_mode = body.output_mode
    await session.flush()
    return {"id": str(model.id), "output_mode": model.output_mode}


@router.get("/configs")
async def list_configs(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """List all subset configs for a project."""
    repo = SubsettingRepository(session)
    configs = await repo.find_by_project_id(project_id)

    # Side-lookup output_mode from the model (Phase 56-04).
    from sqlalchemy import select as _select
    from app.infrastructure.persistence.models.subsetting import SubsetConfigModel
    output_modes: dict = {}
    if configs:
        modes_q = await session.execute(
            _select(SubsetConfigModel.id, SubsetConfigModel.output_mode).where(
                SubsetConfigModel.id.in_([c.id for c in configs])
            )
        )
        output_modes = {row[0]: row[1] for row in modes_q.all()}

    return {"configs": [
        {
            "id": str(c.id),
            "name": c.name,
            "source_connection_id": str(c.source_connection_id) if c.source_connection_id else None,
            "target_connection_id": str(c.target_connection_id) if c.target_connection_id else None,
            "target_percentage": c.target_percentage,
            "target_row_count": c.target_row_count,
            "root_tables": c.root_tables,
            "traversal_strategy": c.traversal_strategy,
            "output_mode": output_modes.get(c.id, "same_database"),
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }
        for c in configs
    ]}


@router.post("/configs", status_code=201)
async def create_config(
    project_id: uuid.UUID, body: SubsetConfigCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    if body.output_mode not in ALLOWED_OUTPUT_MODES:
        raise HTTPException(
            400,
            {
                "error": "invalid_output_mode",
                "detail": f"output_mode must be one of {sorted(ALLOWED_OUTPUT_MODES)}",
            },
        )
    repo = SubsettingRepository(session)
    handler = CreateConfigHandler(repo)
    config = await handler.handle(CreateSubsetConfigCommand(
        project_id=project_id, name=body.name, source_connection_id=uuid.UUID(body.source_connection_id),
        target_percentage=body.target_percentage, target_row_count=body.target_row_count,
        root_tables=body.root_tables, traversal_strategy=body.traversal_strategy,
        output_mode=body.output_mode,
    ))
    return {"id": str(config.id), "name": config.name, "output_mode": config.output_mode}


@router.post("/analyze")
async def analyze_subset(
    project_id: uuid.UUID, body: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = SubsettingRepository(session)
    handler = AnalyzeHandler(repo, session)
    try:
        analysis = await handler.handle(AnalyzeSubsetCommand(config_id=uuid.UUID(body.config_id)))
    except NotFoundError as exc:
        raise HTTPException(404, {"error": "not_found", "detail": str(exc)})
    except Exception as exc:
        logger.exception("subset_analyze_failed", config_id=body.config_id, error=str(exc))
        raise HTTPException(500, {"error": "analyze_failed", "detail": str(exc)[:500]})
    return {"analysis": analysis, "total_tables": len(analysis)}


@router.post("/execute", status_code=202)
async def execute_subset(
    project_id: uuid.UUID, body: ExecuteRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SubsettingRepository(session)
    handler = ExecuteHandler(repo, session)
    try:
        job_id = await handler.handle(ExecuteSubsetCommand(
            config_id=uuid.UUID(body.config_id), project_id=project_id, user_id=uuid.UUID(current_user["id"]),
        ))
    except NotFoundError:
        raise HTTPException(404, {"error": "not_found", "detail": "Config not found"})
    return {"job_id": str(job_id), "status": "pending"}
