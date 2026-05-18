"""Unified Database View endpoints (Phase 50, expanded for connector parity).

Combines read-only discovery output with the project's masking-rule state into
a single, paginated list. The same endpoints power the Database Viewer tab in
the frontend and the bulk-apply toolbar.

Companion endpoints for browsing project file schemas live in
``file_schema_view.py`` — they share the ``DatabaseColumnRow`` shape so the
File Viewer tab can render through the same column-inventory table.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._masking_common import (
    GENERATOR_CHOICES,
    get_or_create_default_policy,
)
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.connection import ConnectionModel
from app.infrastructure.persistence.models.discovery import (
    DiscoveredColumnModel,
    DiscoveredSchemaModel,
    DiscoveredTableModel,
)
from app.infrastructure.persistence.models.generator_preset import GeneratorPresetModel
from app.infrastructure.persistence.models.masking import (
    MaskingPolicyModel,
    MaskingRuleModel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/database",
    tags=["database-view"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


MAX_PAGE_LIMIT = 2000
DEFAULT_PAGE_LIMIT = 500


class PresetChoice(BaseModel):
    id: str
    name: str
    generator_type: str


class DatabaseColumnRow(BaseModel):
    schema_name: str
    table_name: str
    column_id: str
    column_name: str
    data_type: str
    pii_type: str
    pii_confidence: float | None
    status: str  # "not_sensitive" | "protected" | "unprotected"
    current_generator: str | None
    current_preset_id: str | None = None
    rule_id: str | None
    # Connector context — lets the frontend group by source and render
    # connector-specific affordances (mixed-type badge, stale row count).
    connection_id: str
    connection_name: str
    connector_type: str
    # Optional connector-specific signals — None when not applicable.
    mixed_types: list[str] | None = None
    row_count_stale: bool | None = None


class DatabaseViewResponse(BaseModel):
    columns: list[DatabaseColumnRow]
    total_count: int
    limit: int
    offset: int
    has_more: bool
    generator_choices: list[str]
    presets: list[PresetChoice]


class UpsertRuleRequest(BaseModel):
    masking_type: str | None = None
    preset_id: str | None = None  # if set, masking_type is taken from the preset


class UpsertRuleResponse(BaseModel):
    rule_id: str
    masking_type: str
    preset_id: str | None = None
    status: str  # "created" | "updated"


class BulkRuleRequest(BaseModel):
    column_ids: list[str] = Field(..., min_length=1)
    masking_type: str | None = None
    preset_id: str | None = None


class BulkRuleResult(BaseModel):
    column_id: str
    status: str  # "created" | "updated" | "skipped"
    rule_id: str | None = None
    error: str | None = None


class BulkRuleResponse(BaseModel):
    results: list[BulkRuleResult]
    applied: int
    skipped: int


def _column_join():
    """Build the JOIN that exposes connector context alongside discovery rows."""
    return (
        select(
            DiscoveredSchemaModel.schema_name,
            DiscoveredTableModel.table_name,
            DiscoveredTableModel.row_count,
            DiscoveredTableModel.size_bytes,
            DiscoveredColumnModel.id,
            DiscoveredColumnModel.column_name,
            DiscoveredColumnModel.data_type,
            DiscoveredColumnModel.pii_type,
            DiscoveredColumnModel.pii_confidence,
            DiscoveredColumnModel.stats,
            ConnectionModel.id.label("connection_id"),
            ConnectionModel.name.label("connection_name"),
            ConnectionModel.connector_type,
        )
        .join(
            DiscoveredTableModel,
            DiscoveredTableModel.id == DiscoveredColumnModel.table_id,
        )
        .join(
            DiscoveredSchemaModel,
            DiscoveredSchemaModel.id == DiscoveredTableModel.schema_id,
        )
        .join(
            ConnectionModel,
            ConnectionModel.id == DiscoveredSchemaModel.connection_id,
        )
    )


@router.get("", response_model=DatabaseViewResponse)
async def list_columns(
    project_id: uuid.UUID,
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
    connection_id: str | None = Query(
        None,
        description="Restrict to one connection. Useful for multi-connection projects.",
    ),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """List columns for the project, paginated, with connector context."""
    base_filter = ConnectionModel.project_id == project_id
    conn_filter = None
    if connection_id:
        try:
            conn_uuid = uuid.UUID(connection_id)
        except ValueError:
            raise HTTPException(
                400, {"error": "invalid_connection_id", "detail": "Not a UUID"}
            )
        conn_filter = ConnectionModel.id == conn_uuid

    # 1. Total count (so the UI can render "showing N of M" + paging controls).
    count_q = (
        select(func.count(DiscoveredColumnModel.id))
        .join(
            DiscoveredTableModel,
            DiscoveredTableModel.id == DiscoveredColumnModel.table_id,
        )
        .join(
            DiscoveredSchemaModel,
            DiscoveredSchemaModel.id == DiscoveredTableModel.schema_id,
        )
        .join(
            ConnectionModel,
            ConnectionModel.id == DiscoveredSchemaModel.connection_id,
        )
        .where(base_filter)
    )
    if conn_filter is not None:
        count_q = count_q.where(conn_filter)
    total = int((await session.execute(count_q)).scalar_one() or 0)

    # 2. Paginated column window joined to connector context.
    cols_query = (
        _column_join()
        .where(base_filter)
        .order_by(
            ConnectionModel.name,
            DiscoveredSchemaModel.schema_name,
            DiscoveredTableModel.table_name,
            DiscoveredColumnModel.column_name,
        )
        .limit(limit)
        .offset(offset)
    )
    if conn_filter is not None:
        cols_query = cols_query.where(conn_filter)
    cols_result = await session.execute(cols_query)
    column_rows = list(cols_result.all())

    # 3. Existing masking rules keyed by column_id.
    column_ids = [row[4] for row in column_rows]
    rule_by_column: dict[uuid.UUID, tuple[uuid.UUID, str, uuid.UUID | None]] = {}
    if column_ids:
        rules_result = await session.execute(
            select(
                MaskingRuleModel.id,
                MaskingRuleModel.column_id,
                MaskingRuleModel.masking_type,
                MaskingRuleModel.preset_id,
            )
            .join(
                MaskingPolicyModel,
                MaskingPolicyModel.id == MaskingRuleModel.policy_id,
            )
            .where(
                MaskingPolicyModel.project_id == project_id,
                MaskingRuleModel.column_id.in_(column_ids),
            )
        )
        for rule_id, col_id, mtype, preset_id in rules_result.all():
            if col_id is not None:
                rule_by_column[col_id] = (rule_id, mtype, preset_id)

    # 4. Presets (shared across the project).
    presets_q = await session.execute(
        select(GeneratorPresetModel).order_by(GeneratorPresetModel.name)
    )
    presets = [
        PresetChoice(id=str(p.id), name=p.name, generator_type=p.generator_type)
        for p in presets_q.scalars().all()
    ]

    # 5. Assemble response rows.
    out: list[DatabaseColumnRow] = []
    for row in column_rows:
        (
            schema_name,
            table_name,
            _row_count,
            _size_bytes,
            col_id,
            col_name,
            data_type,
            pii_type,
            pii_confidence,
            stats,
            connection_id_val,
            connection_name,
            connector_type,
        ) = row
        rule = rule_by_column.get(col_id)
        if pii_type == "none":
            status = "not_sensitive"
        elif rule is not None:
            status = "protected"
        else:
            status = "unprotected"
        confidence_score = None
        if pii_confidence and isinstance(pii_confidence, dict):
            confidence_score = pii_confidence.get("score")
        mixed_types = None
        row_count_stale = None
        if isinstance(stats, dict):
            mt = stats.get("mixed_types")
            if isinstance(mt, list) and mt:
                mixed_types = [str(t) for t in mt]
            rcs = stats.get("row_count_stale")
            if isinstance(rcs, bool):
                row_count_stale = rcs
        out.append(
            DatabaseColumnRow(
                schema_name=schema_name,
                table_name=table_name,
                column_id=str(col_id),
                column_name=col_name,
                data_type=data_type,
                pii_type=pii_type,
                pii_confidence=confidence_score,
                status=status,
                current_generator=rule[1] if rule else None,
                current_preset_id=str(rule[2]) if rule and rule[2] is not None else None,
                rule_id=str(rule[0]) if rule else None,
                connection_id=str(connection_id_val),
                connection_name=connection_name,
                connector_type=connector_type,
                mixed_types=mixed_types,
                row_count_stale=row_count_stale,
            )
        )

    return DatabaseViewResponse(
        columns=out,
        total_count=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(out) < total,
        generator_choices=GENERATOR_CHOICES,
        presets=presets,
    )


async def _resolve_masking_type(
    session: AsyncSession, masking_type: str | None, preset_id: str | None
) -> tuple[str, uuid.UUID | None]:
    """Validate and return ``(masking_type, preset_id)`` for rule writes."""
    resolved_preset_id: uuid.UUID | None = None
    if preset_id:
        try:
            preset_uuid = uuid.UUID(preset_id)
        except ValueError:
            raise HTTPException(
                400, {"error": "invalid_preset_id", "detail": "Not a UUID"}
            )
        preset_lookup = await session.execute(
            select(GeneratorPresetModel).where(GeneratorPresetModel.id == preset_uuid)
        )
        preset = preset_lookup.scalar_one_or_none()
        if preset is None:
            raise HTTPException(404, {"error": "preset_not_found"})
        masking_type = preset.generator_type
        resolved_preset_id = preset.id
    elif masking_type is None:
        raise HTTPException(
            400,
            {"error": "missing_field", "detail": "Provide masking_type or preset_id"},
        )

    if masking_type not in GENERATOR_CHOICES:
        raise HTTPException(
            400,
            {
                "error": "invalid_generator",
                "detail": f"masking_type must be one of {GENERATOR_CHOICES}",
            },
        )
    return masking_type, resolved_preset_id


async def _upsert_rule_for_column(
    session: AsyncSession,
    project_id: uuid.UUID,
    column_id: uuid.UUID,
    masking_type: str,
    preset_id: uuid.UUID | None,
) -> tuple[MaskingRuleModel, str]:
    """Create-or-update a rule for one column. Caller validates inputs."""
    rule_lookup = await session.execute(
        select(MaskingRuleModel)
        .join(
            MaskingPolicyModel,
            MaskingPolicyModel.id == MaskingRuleModel.policy_id,
        )
        .where(
            MaskingPolicyModel.project_id == project_id,
            MaskingRuleModel.column_id == column_id,
        )
        .limit(1)
    )
    existing_rule = rule_lookup.scalar_one_or_none()

    if existing_rule is not None:
        existing_rule.masking_type = masking_type
        existing_rule.preset_id = preset_id
        await session.flush()
        return existing_rule, "updated"

    policy_id = await get_or_create_default_policy(session, project_id)
    new_rule = MaskingRuleModel(
        id=uuid.uuid4(),
        policy_id=policy_id,
        column_id=column_id,
        match_pattern=None,
        masking_type=masking_type,
        masking_config={},
        preserve_format=False,
        deterministic=False,
        preset_id=preset_id,
    )
    session.add(new_rule)
    await session.flush()
    return new_rule, "created"


@router.post("/columns/{column_id}/rule", response_model=UpsertRuleResponse)
async def upsert_rule(
    project_id: uuid.UUID,
    column_id: uuid.UUID,
    body: UpsertRuleRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Upsert a masking rule for the given column. Idempotent."""
    masking_type, resolved_preset_id = await _resolve_masking_type(
        session, body.masking_type, body.preset_id
    )

    existing_col = await session.execute(
        select(DiscoveredColumnModel.id)
        .join(
            DiscoveredTableModel,
            DiscoveredTableModel.id == DiscoveredColumnModel.table_id,
        )
        .join(
            DiscoveredSchemaModel,
            DiscoveredSchemaModel.id == DiscoveredTableModel.schema_id,
        )
        .join(
            ConnectionModel,
            ConnectionModel.id == DiscoveredSchemaModel.connection_id,
        )
        .where(
            DiscoveredColumnModel.id == column_id,
            ConnectionModel.project_id == project_id,
        )
    )
    if existing_col.scalar_one_or_none() is None:
        raise HTTPException(
            404, {"error": "not_found", "detail": "Column not in this project"}
        )

    rule, status = await _upsert_rule_for_column(
        session, project_id, column_id, masking_type, resolved_preset_id
    )
    await logger.ainfo(
        "database_view_rule_" + status,
        project_id=str(project_id),
        column_id=str(column_id),
        masking_type=masking_type,
        preset_id=str(resolved_preset_id) if resolved_preset_id else None,
    )
    return UpsertRuleResponse(
        rule_id=str(rule.id),
        masking_type=rule.masking_type,
        preset_id=str(rule.preset_id) if rule.preset_id else None,
        status=status,
    )


@router.post("/columns/bulk-rule", response_model=BulkRuleResponse)
async def bulk_apply_rule(
    project_id: uuid.UUID,
    body: BulkRuleRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Apply the same masking rule to many columns in one transaction.

    Columns that don't belong to this project are reported under
    ``results[].status == "skipped"`` rather than aborting the whole call,
    so a stale column_id in the UI selection doesn't lose the rest of the
    user's work.
    """
    masking_type, resolved_preset_id = await _resolve_masking_type(
        session, body.masking_type, body.preset_id
    )

    requested_ids: list[uuid.UUID] = []
    invalid: list[BulkRuleResult] = []
    for raw in body.column_ids:
        try:
            requested_ids.append(uuid.UUID(raw))
        except ValueError:
            invalid.append(
                BulkRuleResult(column_id=raw, status="skipped", error="invalid_uuid")
            )

    if not requested_ids:
        return BulkRuleResponse(results=invalid, applied=0, skipped=len(invalid))

    valid_rows = await session.execute(
        select(DiscoveredColumnModel.id)
        .join(
            DiscoveredTableModel,
            DiscoveredTableModel.id == DiscoveredColumnModel.table_id,
        )
        .join(
            DiscoveredSchemaModel,
            DiscoveredSchemaModel.id == DiscoveredTableModel.schema_id,
        )
        .join(
            ConnectionModel,
            ConnectionModel.id == DiscoveredSchemaModel.connection_id,
        )
        .where(
            DiscoveredColumnModel.id.in_(requested_ids),
            ConnectionModel.project_id == project_id,
        )
    )
    valid_set = {row[0] for row in valid_rows.all()}

    results: list[BulkRuleResult] = list(invalid)
    applied = 0
    for col_id in requested_ids:
        if col_id not in valid_set:
            results.append(
                BulkRuleResult(
                    column_id=str(col_id),
                    status="skipped",
                    error="not_in_project",
                )
            )
            continue
        rule, status = await _upsert_rule_for_column(
            session, project_id, col_id, masking_type, resolved_preset_id
        )
        applied += 1
        results.append(
            BulkRuleResult(column_id=str(col_id), status=status, rule_id=str(rule.id))
        )

    await logger.ainfo(
        "database_view_bulk_rule_applied",
        project_id=str(project_id),
        applied=applied,
        skipped=len(results) - applied,
        masking_type=masking_type,
    )
    return BulkRuleResponse(results=results, applied=applied, skipped=len(results) - applied)


@router.delete("/columns/{column_id}/rule", status_code=204)
async def remove_rule(
    project_id: uuid.UUID,
    column_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Remove all masking rules for this column in this project."""
    rules_query = (
        select(MaskingRuleModel.id)
        .join(
            MaskingPolicyModel,
            MaskingPolicyModel.id == MaskingRuleModel.policy_id,
        )
        .where(
            MaskingPolicyModel.project_id == project_id,
            MaskingRuleModel.column_id == column_id,
        )
    )
    rule_ids = [r[0] for r in (await session.execute(rules_query)).all()]
    if not rule_ids:
        return  # Idempotent — nothing to remove.

    await session.execute(
        delete(MaskingRuleModel).where(MaskingRuleModel.id.in_(rule_ids))
    )
    await session.flush()
    await logger.ainfo(
        "database_view_rule_removed",
        project_id=str(project_id),
        column_id=str(column_id),
        removed=len(rule_ids),
    )
