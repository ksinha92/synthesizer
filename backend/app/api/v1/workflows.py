"""Workflow API endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.workflow.commands import CreateWorkflowCommand, ExecuteWorkflowCommand
from app.application.workflow.handlers import CreateWorkflowHandler, ExecuteWorkflowHandler
from app.domain.shared.errors import NotFoundError
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.workflow_repo import WorkflowRepository

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/workflows",
    tags=["workflows"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    dag_definition: dict = Field(default_factory=lambda: {"nodes": [], "edges": []})


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    is_active: bool
    created_at: str


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    project_id: uuid.UUID, body: WorkflowCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = WorkflowRepository(session)
    handler = CreateWorkflowHandler(repo)
    try:
        wf = await handler.handle(CreateWorkflowCommand(
            project_id=project_id, name=body.name, description=body.description,
            dag_definition=body.dag_definition,
        ))
    except ValueError as e:
        raise HTTPException(400, {"error": "invalid_dag", "detail": str(e)})
    return WorkflowResponse(id=str(wf.id), name=wf.name, description=wf.description, is_active=wf.is_active, created_at=wf.created_at.isoformat() if wf.created_at else "")


@router.get("")
async def list_workflows(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = WorkflowRepository(session)
    workflows = await repo.find_by_project_id(project_id)
    return {"workflows": [
        WorkflowResponse(id=str(w.id), name=w.name, description=w.description, is_active=w.is_active, created_at=w.created_at.isoformat() if w.created_at else "").model_dump()
        for w in workflows
    ]}


@router.get("/{workflow_id}")
async def get_workflow(
    project_id: uuid.UUID, workflow_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = WorkflowRepository(session)
    wf = await repo.get(workflow_id)
    if not wf or wf.project_id != project_id:
        raise HTTPException(404, {"error": "not_found"})
    return {"id": str(wf.id), "name": wf.name, "description": wf.description, "dag_definition": wf.dag_definition, "is_active": wf.is_active}


@router.get("/{workflow_id}/executions")
async def list_workflow_executions(
    project_id: uuid.UUID, workflow_id: uuid.UUID,
    page: int = 1, page_size: int = 20,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """List execution history for a workflow (jobs of type 'workflow')."""
    from sqlalchemy import func, select as sa_select
    from app.infrastructure.persistence.models.job import JobModel

    base_filter = [
        JobModel.project_id == project_id,
        JobModel.job_type == "workflow",
        JobModel.reference_id == workflow_id,
    ]

    count_query = sa_select(func.count()).select_from(JobModel).where(*base_filter)
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    query = (
        sa_select(JobModel)
        .where(*base_filter)
        .order_by(JobModel.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    result = await session.execute(query)

    items = [
        {
            "id": str(j.id),
            "status": j.status,
            "progress": j.progress,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat() if j.created_at else "",
        }
        for j in result.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{workflow_id}/execute", status_code=202)
async def execute_workflow(
    project_id: uuid.UUID, workflow_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = WorkflowRepository(session)
    handler = ExecuteWorkflowHandler(repo, session)
    try:
        job_id = await handler.handle(ExecuteWorkflowCommand(
            workflow_id=workflow_id, project_id=project_id, user_id=uuid.UUID(current_user["id"]),
        ))
    except NotFoundError:
        raise HTTPException(404, {"error": "not_found"})
    return {"job_id": str(job_id), "status": "pending"}
