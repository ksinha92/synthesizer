"""Sensitivity rules CRUD (Phase 52).

Global, prioritized PII detectors that complement the built-in 4-layer
pipeline. Rules are evaluated in priority order (lower number first);
the first match wins.
"""

from __future__ import annotations

import re
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_editor, require_viewer
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.sensitivity_rule import SensitivityRuleModel

logger = structlog.get_logger()
router = APIRouter(prefix="/sensitivity-rules", tags=["sensitivity-rules"])


ALLOWED_MATCH_TYPES = {"column_name_regex", "column_name_contains", "value_regex"}
ALLOWED_PII_TYPES = {
    "email", "phone", "ssn", "person_name", "address", "credit_card",
    "ip_address", "date_of_birth", "financial_account", "medical_record",
    "other",
}


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    match_type: str
    pattern: str = Field(..., min_length=1)
    suggested_pii_type: str
    suggested_preset_id: str | None = None
    priority: int = 100
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    match_type: str | None = None
    pattern: str | None = None
    suggested_pii_type: str | None = None
    suggested_preset_id: str | None = None
    priority: int | None = None
    enabled: bool | None = None


class RuleResponse(BaseModel):
    id: str
    name: str
    description: str
    match_type: str
    pattern: str
    suggested_pii_type: str
    suggested_preset_id: str | None
    priority: int
    enabled: bool
    created_at: str | None
    updated_at: str | None


def _validate(match_type: str | None, pii_type: str | None, pattern: str | None) -> None:
    if match_type is not None and match_type not in ALLOWED_MATCH_TYPES:
        raise HTTPException(
            400,
            {
                "error": "invalid_match_type",
                "detail": f"match_type must be one of {sorted(ALLOWED_MATCH_TYPES)}",
            },
        )
    if pii_type is not None and pii_type not in ALLOWED_PII_TYPES:
        raise HTTPException(
            400,
            {
                "error": "invalid_pii_type",
                "detail": f"suggested_pii_type must be one of {sorted(ALLOWED_PII_TYPES)}",
            },
        )
    if pattern is not None and match_type in {"column_name_regex", "value_regex"}:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise HTTPException(
                400,
                {"error": "invalid_regex", "detail": f"pattern is not valid regex: {exc}"},
            )


def _to_response(m: SensitivityRuleModel) -> RuleResponse:
    return RuleResponse(
        id=str(m.id),
        name=m.name,
        description=m.description or "",
        match_type=m.match_type,
        pattern=m.pattern,
        suggested_pii_type=m.suggested_pii_type,
        suggested_preset_id=str(m.suggested_preset_id) if m.suggested_preset_id else None,
        priority=m.priority,
        enabled=m.enabled,
        created_at=m.created_at.isoformat() if m.created_at else None,
        updated_at=m.updated_at.isoformat() if m.updated_at else None,
    )


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_viewer),
):
    """List rules ordered by priority (lower first), then by name."""
    result = await session.execute(
        select(SensitivityRuleModel).order_by(
            SensitivityRuleModel.priority,
            SensitivityRuleModel.name,
        )
    )
    return [_to_response(r) for r in result.scalars().all()]


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(
    body: RuleCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_editor),
):
    _validate(body.match_type, body.suggested_pii_type, body.pattern)
    rule = SensitivityRuleModel(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        match_type=body.match_type,
        pattern=body.pattern,
        suggested_pii_type=body.suggested_pii_type,
        suggested_preset_id=uuid.UUID(body.suggested_preset_id) if body.suggested_preset_id else None,
        priority=body.priority,
        enabled=body.enabled,
    )
    session.add(rule)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            409,
            {"error": "duplicate_name", "detail": f"Rule with name {body.name!r} already exists"},
        )
    await logger.ainfo("sensitivity_rule_created", rule_id=str(rule.id), name=rule.name)
    return _to_response(rule)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_viewer),
):
    result = await session.execute(
        select(SensitivityRuleModel).where(SensitivityRuleModel.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Rule not found"})
    return _to_response(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_editor),
):
    _validate(body.match_type, body.suggested_pii_type, body.pattern)
    result = await session.execute(
        select(SensitivityRuleModel).where(SensitivityRuleModel.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Rule not found"})

    for field in ("name", "description", "match_type", "pattern", "suggested_pii_type",
                  "priority", "enabled"):
        value = getattr(body, field)
        if value is not None:
            setattr(rule, field, value)
    if body.suggested_preset_id is not None:
        rule.suggested_preset_id = (
            uuid.UUID(body.suggested_preset_id) if body.suggested_preset_id else None
        )

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            409,
            {"error": "duplicate_name", "detail": "Another rule already uses that name"},
        )
    await logger.ainfo("sensitivity_rule_updated", rule_id=str(rule_id), name=rule.name)
    return _to_response(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_editor),
):
    result = await session.execute(
        select(SensitivityRuleModel).where(SensitivityRuleModel.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Rule not found"})

    await session.execute(
        delete(SensitivityRuleModel).where(SensitivityRuleModel.id == rule_id)
    )
    await session.flush()
    await logger.ainfo("sensitivity_rule_deleted", rule_id=str(rule_id))
