"""Generator presets CRUD (Phase 51).

Presets are global by design: one shared vocabulary across all projects.
Masking rules optionally reference a preset via the `preset_id` FK
(ON DELETE SET NULL — removing a preset unlinks but does not delete rules).
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_editor, require_viewer
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.generator_preset import GeneratorPresetModel
from app.infrastructure.persistence.models.masking import MaskingRuleModel

logger = structlog.get_logger()
router = APIRouter(prefix="/generator-presets", tags=["generator-presets"])


# Allowed generator types — single source of truth lives in _masking_common
# so the Database View dropdown and the Presets API never drift apart.
from app.api.v1._masking_common import ALLOWED_GENERATOR_TYPES  # noqa: E402,F401


class PresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    generator_type: str
    config: dict = Field(default_factory=dict)
    consistency: bool = False


class PresetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    generator_type: str | None = None
    config: dict | None = None
    consistency: bool | None = None


class PresetResponse(BaseModel):
    id: str
    name: str
    description: str
    generator_type: str
    config: dict
    consistency: bool
    occurrences: int
    created_at: str | None
    updated_at: str | None


def _validate_generator_type(value: str) -> None:
    if value not in ALLOWED_GENERATOR_TYPES:
        raise HTTPException(
            400,
            {
                "error": "invalid_generator_type",
                "detail": f"generator_type must be one of {sorted(ALLOWED_GENERATOR_TYPES)}",
            },
        )


async def _occurrences_by_preset(session: AsyncSession) -> dict[uuid.UUID, int]:
    """Count how many masking_rules reference each preset."""
    result = await session.execute(
        select(MaskingRuleModel.preset_id, func.count(MaskingRuleModel.id))
        .where(MaskingRuleModel.preset_id.is_not(None))
        .group_by(MaskingRuleModel.preset_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


def _to_response(model: GeneratorPresetModel, occurrences: int) -> PresetResponse:
    return PresetResponse(
        id=str(model.id),
        name=model.name,
        description=model.description or "",
        generator_type=model.generator_type,
        config=model.config or {},
        consistency=model.consistency,
        occurrences=occurrences,
        created_at=model.created_at.isoformat() if model.created_at else None,
        updated_at=model.updated_at.isoformat() if model.updated_at else None,
    )


@router.get("", response_model=list[PresetResponse])
async def list_presets(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_viewer),
):
    """List all presets with their per-rule occurrence count."""
    result = await session.execute(
        select(GeneratorPresetModel).order_by(GeneratorPresetModel.name)
    )
    occ = await _occurrences_by_preset(session)
    return [_to_response(p, occ.get(p.id, 0)) for p in result.scalars().all()]


@router.post("", response_model=PresetResponse, status_code=201)
async def create_preset(
    body: PresetCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_editor),
):
    """Create a new preset. Name must be unique."""
    _validate_generator_type(body.generator_type)

    preset = GeneratorPresetModel(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        generator_type=body.generator_type,
        config=body.config,
        consistency=body.consistency,
    )
    session.add(preset)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            409,
            {"error": "duplicate_name", "detail": f"Preset with name {body.name!r} already exists"},
        )
    await logger.ainfo("preset_created", preset_id=str(preset.id), name=preset.name)
    return _to_response(preset, 0)


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(
    preset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_viewer),
):
    result = await session.execute(
        select(GeneratorPresetModel).where(GeneratorPresetModel.id == preset_id)
    )
    preset = result.scalar_one_or_none()
    if preset is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Preset not found"})
    occ = await _occurrences_by_preset(session)
    return _to_response(preset, occ.get(preset_id, 0))


@router.put("/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: uuid.UUID,
    body: PresetUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_editor),
):
    result = await session.execute(
        select(GeneratorPresetModel).where(GeneratorPresetModel.id == preset_id)
    )
    preset = result.scalar_one_or_none()
    if preset is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Preset not found"})

    if body.generator_type is not None:
        _validate_generator_type(body.generator_type)
        preset.generator_type = body.generator_type
    if body.name is not None:
        preset.name = body.name
    if body.description is not None:
        preset.description = body.description
    if body.config is not None:
        preset.config = body.config
    if body.consistency is not None:
        preset.consistency = body.consistency

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            409,
            {"error": "duplicate_name", "detail": "Another preset already uses that name"},
        )

    occ = await _occurrences_by_preset(session)
    await logger.ainfo("preset_updated", preset_id=str(preset_id), name=preset.name)
    return _to_response(preset, occ.get(preset_id, 0))


@router.delete("/{preset_id}", status_code=204)
async def delete_preset(
    preset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _role: dict = Depends(require_editor),
):
    """Delete a preset. Existing rules referencing it become unlinked
    (preset_id → NULL via ON DELETE SET NULL from migration 017).
    """
    result = await session.execute(
        select(GeneratorPresetModel).where(GeneratorPresetModel.id == preset_id)
    )
    preset = result.scalar_one_or_none()
    if preset is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Preset not found"})

    await session.execute(
        delete(GeneratorPresetModel).where(GeneratorPresetModel.id == preset_id)
    )
    await session.flush()
    await logger.ainfo("preset_deleted", preset_id=str(preset_id), name=preset.name)
