"""Masking API endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.masking.commands import *
from app.application.masking.handlers import *
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.masking_repo import SQLAlchemyMaskingRepository

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/masking",
    tags=["masking"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


class PolicyCreate(BaseModel):
    name: str
    description: str = ""
    is_default: bool = False


class RuleCreate(BaseModel):
    column_id: str | None = None
    match_pattern: dict | None = None
    masking_type: str = "redact"
    masking_config: dict = Field(default_factory=dict)
    preserve_format: bool = False
    deterministic: bool = False
    # Phase 53/58: linked-column joint generation + consistency-group identity.
    linked_column_ids: list[uuid.UUID] | None = None
    consistency_group: str | None = None


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: str
    is_default: bool
    created_at: str


class ExecuteRequest(BaseModel):
    policy_id: str
    connection_id: str


class AutoSuggestRequest(BaseModel):
    schema_id: str


@router.get("/policies")
async def list_policies(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = SQLAlchemyMaskingRepository(session)
    policies = await repo.find_by_project_id(project_id)
    return {"policies": [
        PolicyResponse(id=str(p.id), name=p.name, description=p.description, is_default=p.is_default, created_at=p.created_at.isoformat() if p.created_at else "").model_dump()
        for p in policies
    ]}


@router.post("/policies", response_model=PolicyResponse, status_code=201)
async def create_policy(
    project_id: uuid.UUID, body: PolicyCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyMaskingRepository(session)
    handler = CreatePolicyHandler(repo)
    policy = await handler.handle(CreatePolicyCommand(project_id=project_id, name=body.name, description=body.description, is_default=body.is_default))
    return PolicyResponse(id=str(policy.id), name=policy.name, description=policy.description, is_default=policy.is_default, created_at=policy.created_at.isoformat() if policy.created_at else "")


@router.post("/policies/{policy_id}/rules", status_code=201)
async def add_rule(
    project_id: uuid.UUID, policy_id: uuid.UUID, body: RuleCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyMaskingRepository(session)
    handler = AddRuleHandler(repo)
    rule = await handler.handle(AddRuleCommand(
        policy_id=policy_id, column_id=uuid.UUID(body.column_id) if body.column_id else None,
        match_pattern=body.match_pattern, masking_type=body.masking_type,
        masking_config=body.masking_config, preserve_format=body.preserve_format, deterministic=body.deterministic,
        linked_column_ids=list(body.linked_column_ids or []),
        consistency_group=body.consistency_group,
    ))
    return {
        "id": str(rule.id),
        "masking_type": rule.masking_type.value,
        "linked_column_ids": [str(c) for c in (rule.linked_column_ids or [])],
        "consistency_group": rule.consistency_group,
    }


class RuleUpdate(BaseModel):
    masking_type: str | None = None
    masking_config: dict | None = None
    preserve_format: bool | None = None
    deterministic: bool | None = None
    # Phase 53/58: linked-column joint generation + consistency-group identity.
    linked_column_ids: list[uuid.UUID] | None = None
    consistency_group: str | None = None


@router.put("/policies/{policy_id}/rules/{rule_id}")
async def update_rule(
    project_id: uuid.UUID, policy_id: uuid.UUID, rule_id: uuid.UUID,
    body: RuleUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Update an existing masking rule. Partial update."""
    repo = SQLAlchemyMaskingRepository(session)
    updated = await repo.update_rule(rule_id, policy_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, {"error": "not_found", "detail": "Rule not found or does not belong to this policy"})

    from app.infrastructure.persistence.sqlalchemy.audit_repo import AuditRepository
    audit = AuditRepository(session)
    await audit.log(
        user_id=uuid.UUID(current_user["id"]) if current_user.get("id") else None,
        project_id=project_id, action="masking_rule_updated",
        resource_type="masking_rule", resource_id=rule_id,
        details=body.model_dump(exclude_none=True),
    )

    return updated


@router.delete("/policies/{policy_id}/rules/{rule_id}", status_code=204)
async def delete_rule(
    project_id: uuid.UUID, policy_id: uuid.UUID, rule_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Delete a masking rule."""
    repo = SQLAlchemyMaskingRepository(session)
    deleted = await repo.delete_rule(rule_id, policy_id)
    if not deleted:
        raise HTTPException(404, {"error": "not_found", "detail": "Rule not found or does not belong to this policy"})

    from app.infrastructure.persistence.sqlalchemy.audit_repo import AuditRepository
    audit = AuditRepository(session)
    await audit.log(
        user_id=uuid.UUID(current_user["id"]) if current_user.get("id") else None,
        project_id=project_id, action="masking_rule_deleted",
        resource_type="masking_rule", resource_id=rule_id,
    )


@router.post("/preview")
async def preview_masking(
    project_id: uuid.UUID, body: ExecuteRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyMaskingRepository(session)
    handler = PreviewHandler(repo)
    result = await handler.handle(PreviewMaskingCommand(
        policy_id=uuid.UUID(body.policy_id), connection_id=uuid.UUID(body.connection_id), table_name="",
    ))
    return {"preview": result}


@router.post("/execute", status_code=202)
async def execute_masking(
    project_id: uuid.UUID, body: ExecuteRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyMaskingRepository(session)
    handler = ExecuteHandler(repo, session)
    job_id = await handler.handle(ExecuteMaskingCommand(
        policy_id=uuid.UUID(body.policy_id), project_id=project_id,
        connection_id=uuid.UUID(body.connection_id), user_id=uuid.UUID(current_user["id"]),
    ))
    return {"job_id": str(job_id), "status": "pending"}


@router.post("/auto-suggest")
async def auto_suggest(
    project_id: uuid.UUID, body: AutoSuggestRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    from app.infrastructure.persistence.sqlalchemy.discovery_repo import SQLAlchemyDiscoveryRepository
    discovery_repo = SQLAlchemyDiscoveryRepository(session)
    handler = AutoSuggestHandler(discovery_repo)
    suggestions = await handler.handle(AutoSuggestRulesCommand(project_id=project_id, schema_id=uuid.UUID(body.schema_id)))
    return {"suggestions": suggestions}
