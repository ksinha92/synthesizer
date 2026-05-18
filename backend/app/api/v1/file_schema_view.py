"""File Viewer tab endpoints — sibling of the Database View.

Surfaces uploaded file schemas (COBOL copybooks, Excel dictionaries, manual
definitions, discovery-derived) as columnar rows in the same
``DatabaseColumnRow`` shape the Database Viewer tab consumes, so the
frontend can render both tabs through a single column-inventory table.

File "columns" don't live in ``discovered_columns`` so we synthesize a
deterministic ``column_id`` per field via ``uuid5(file:{schema_id}:{field_name})``.
Masking rules write that synthetic id into ``masking_rules.column_id`` and
also carry ``match_pattern = {"file_schema_id": ..., "field_name": ...}`` so
the synthetic-generation worker can route the rule back to the right field
without depending on the column-id stability across schema edits.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._masking_common import (
    GENERATOR_CHOICES,
    get_or_create_default_policy,
)
from app.domain.synthetic.file_schema import (
    FILE_COLUMN_NAMESPACE as _DOMAIN_FILE_COLUMN_NAMESPACE,
    file_field_column_id as _domain_file_field_column_id,
)
from app.api.v1.database_view import (
    BulkRuleResponse,
    BulkRuleResult,
    DatabaseColumnRow,
    DatabaseViewResponse,
    PresetChoice,
    UpsertRuleRequest,
    UpsertRuleResponse,
    _resolve_masking_type,
)
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.generator_preset import GeneratorPresetModel
from app.infrastructure.persistence.models.masking import (
    MaskingPolicyModel,
    MaskingRuleModel,
)
from app.infrastructure.persistence.sqlalchemy.file_schema_repo import (
    SQLAlchemyFileSchemaRepository,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/file-schemas",
    tags=["file-schema-view"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


# Namespace used to derive stable synthetic column_ids for file fields.
# Re-exported from the domain layer so the file-set generation worker can
# build the reverse map (column_id → field_name) needed to honor joint
# rules with ``linked_column_ids``.
_FILE_COLUMN_NAMESPACE = _DOMAIN_FILE_COLUMN_NAMESPACE


def _field_column_id(schema_id: str, field_name: str) -> uuid.UUID:
    """Deterministic UUID5 so the same (schema, field) always maps to the same id.

    Re-editing or re-uploading a file schema preserves the column_id, which
    means an existing masking rule keeps pointing at the right field instead
    of being orphaned (the same correctness problem the Database View just
    fixed for SQL connectors).
    """
    return _domain_file_field_column_id(schema_id, field_name)


def _connector_type_for_format(file_format: str) -> str:
    """Render a connector-type tag so the frontend can show a file-type badge."""
    return f"file:{(file_format or 'unknown').lower()}"


def _row_for_field(
    schema_row: dict,
    field: dict,
    rule_by_column: dict[uuid.UUID, tuple[uuid.UUID, str, uuid.UUID | None]],
) -> DatabaseColumnRow:
    schema_id = schema_row["id"]
    field_name = field["name"]
    col_id = _field_column_id(schema_id, field_name)
    rule = rule_by_column.get(col_id)
    pii_type = (field.get("pii_type") or "none") or "none"
    if pii_type == "none":
        status = "not_sensitive"
    elif rule is not None:
        status = "protected"
    else:
        status = "unprotected"
    return DatabaseColumnRow(
        schema_name=schema_row.get("name") or "file",
        table_name=schema_row.get("output_filename") or schema_row.get("name") or "file",
        column_id=str(col_id),
        column_name=field_name,
        data_type=field.get("data_type") or "unknown",
        pii_type=pii_type,
        pii_confidence=None,
        status=status,
        current_generator=rule[1] if rule else None,
        current_preset_id=str(rule[2]) if rule and rule[2] is not None else None,
        rule_id=str(rule[0]) if rule else None,
        connection_id=schema_id,
        connection_name=schema_row.get("name") or "file schema",
        connector_type=_connector_type_for_format(schema_row.get("file_format", "")),
        mixed_types=None,
        row_count_stale=None,
    )


@router.get("/columns", response_model=DatabaseViewResponse)
async def list_file_schema_columns(
    project_id: uuid.UUID,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    file_schema_id: str | None = Query(
        None,
        description="Restrict to a single file schema id.",
    ),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Flatten every uploaded file schema's fields into a paginated column list."""
    repo = SQLAlchemyFileSchemaRepository(session)
    schemas = await repo.list_by_project(project_id)
    if file_schema_id:
        try:
            uuid.UUID(file_schema_id)
        except ValueError:
            raise HTTPException(
                400, {"error": "invalid_file_schema_id", "detail": "Not a UUID"}
            )
        schemas = [s for s in schemas if s["id"] == file_schema_id]

    # Flatten to (schema, field) pairs, sorted for deterministic paging.
    pairs: list[tuple[dict, dict]] = []
    for s in schemas:
        for f in s.get("fields") or []:
            pairs.append((s, f))
    pairs.sort(key=lambda sf: (sf[0].get("name") or "", sf[1].get("name") or ""))

    total = len(pairs)
    window = pairs[offset : offset + limit]

    # Resolve any existing masking rules for the synthetic column_ids in
    # this page so we can render Protected/Unprotected status correctly.
    column_ids = [_field_column_id(s["id"], f["name"]) for s, f in window]
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
        for rid, cid, mtype, pid in rules_result.all():
            if cid is not None:
                rule_by_column[cid] = (rid, mtype, pid)

    presets_q = await session.execute(
        select(GeneratorPresetModel).order_by(GeneratorPresetModel.name)
    )
    presets = [
        PresetChoice(id=str(p.id), name=p.name, generator_type=p.generator_type)
        for p in presets_q.scalars().all()
    ]

    rows = [_row_for_field(s, f, rule_by_column) for s, f in window]

    return DatabaseViewResponse(
        columns=rows,
        total_count=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(rows) < total,
        generator_choices=GENERATOR_CHOICES,
        presets=presets,
    )


class FileFieldRuleRequest(BaseModel):
    file_schema_id: str
    field_name: str = Field(..., min_length=1, max_length=255)
    masking_type: str | None = None
    preset_id: str | None = None


async def _validate_file_field(
    session: AsyncSession,
    project_id: uuid.UUID,
    file_schema_id: str,
    field_name: str,
) -> tuple[uuid.UUID, dict]:
    """Confirm the field exists in a schema this project owns; return ids."""
    try:
        schema_uuid = uuid.UUID(file_schema_id)
    except ValueError:
        raise HTTPException(
            400, {"error": "invalid_file_schema_id", "detail": "Not a UUID"}
        )
    repo = SQLAlchemyFileSchemaRepository(session)
    schema = await repo.get(schema_uuid)
    if not schema or schema.get("project_id") != str(project_id):
        raise HTTPException(404, {"error": "not_found", "detail": "Schema not in this project"})
    field = next(
        (f for f in (schema.get("fields") or []) if f.get("name") == field_name),
        None,
    )
    if field is None:
        raise HTTPException(
            404, {"error": "field_not_found", "detail": f"No field '{field_name}'"}
        )
    return _field_column_id(file_schema_id, field_name), schema


async def _upsert_file_rule(
    session: AsyncSession,
    project_id: uuid.UUID,
    column_id: uuid.UUID,
    file_schema_id: str,
    field_name: str,
    masking_type: str,
    preset_id: uuid.UUID | None,
) -> tuple[MaskingRuleModel, str]:
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
    existing = rule_lookup.scalar_one_or_none()
    match_pattern = {
        "kind": "file_field",
        "file_schema_id": file_schema_id,
        "field_name": field_name,
    }
    if existing is not None:
        existing.masking_type = masking_type
        existing.preset_id = preset_id
        existing.match_pattern = match_pattern
        await session.flush()
        return existing, "updated"

    policy_id = await get_or_create_default_policy(session, project_id)
    new_rule = MaskingRuleModel(
        id=uuid.uuid4(),
        policy_id=policy_id,
        column_id=column_id,
        match_pattern=match_pattern,
        masking_type=masking_type,
        masking_config={},
        preserve_format=False,
        deterministic=False,
        preset_id=preset_id,
    )
    session.add(new_rule)
    await session.flush()
    return new_rule, "created"


@router.post("/columns/rule", response_model=UpsertRuleResponse)
async def upsert_file_field_rule(
    project_id: uuid.UUID,
    body: FileFieldRuleRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Assign a masking rule to a single field in a file schema."""
    masking_type, resolved_preset_id = await _resolve_masking_type(
        session, body.masking_type, body.preset_id
    )
    column_id, _ = await _validate_file_field(
        session, project_id, body.file_schema_id, body.field_name
    )
    rule, status = await _upsert_file_rule(
        session,
        project_id,
        column_id,
        body.file_schema_id,
        body.field_name,
        masking_type,
        resolved_preset_id,
    )
    await logger.ainfo(
        "file_schema_view_rule_" + status,
        project_id=str(project_id),
        file_schema_id=body.file_schema_id,
        field_name=body.field_name,
        masking_type=masking_type,
    )
    return UpsertRuleResponse(
        rule_id=str(rule.id),
        masking_type=rule.masking_type,
        preset_id=str(rule.preset_id) if rule.preset_id else None,
        status=status,
    )


class BulkFileFieldRuleRequest(BaseModel):
    fields: list[FileFieldRuleRequest] = Field(..., min_length=1)
    masking_type: str | None = None
    preset_id: str | None = None


@router.post("/columns/bulk-rule", response_model=BulkRuleResponse)
async def bulk_apply_file_field_rule(
    project_id: uuid.UUID,
    body: BulkFileFieldRuleRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Apply the same masking rule to many file-schema fields in one call."""
    masking_type, resolved_preset_id = await _resolve_masking_type(
        session, body.masking_type, body.preset_id
    )
    results: list[BulkRuleResult] = []
    applied = 0
    for f in body.fields:
        try:
            column_id, _ = await _validate_file_field(
                session, project_id, f.file_schema_id, f.field_name
            )
        except HTTPException as exc:
            results.append(
                BulkRuleResult(
                    column_id=f"{f.file_schema_id}:{f.field_name}",
                    status="skipped",
                    error=str(exc.detail.get("error") if isinstance(exc.detail, dict) else exc.detail),
                )
            )
            continue
        rule, status = await _upsert_file_rule(
            session,
            project_id,
            column_id,
            f.file_schema_id,
            f.field_name,
            masking_type,
            resolved_preset_id,
        )
        applied += 1
        results.append(
            BulkRuleResult(column_id=str(column_id), status=status, rule_id=str(rule.id))
        )

    await logger.ainfo(
        "file_schema_view_bulk_rule_applied",
        project_id=str(project_id),
        applied=applied,
        skipped=len(results) - applied,
        masking_type=masking_type,
    )
    return BulkRuleResponse(
        results=results,
        applied=applied,
        skipped=len(results) - applied,
    )


@router.delete("/columns/rule", status_code=204)
async def remove_file_field_rule(
    project_id: uuid.UUID,
    file_schema_id: str = Query(...),
    field_name: str = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Clear the masking rule for a single file-schema field. Idempotent."""
    column_id, _ = await _validate_file_field(
        session, project_id, file_schema_id, field_name
    )
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
        return
    await session.execute(
        delete(MaskingRuleModel).where(MaskingRuleModel.id.in_(rule_ids))
    )
    await session.flush()
    await logger.ainfo(
        "file_schema_view_rule_removed",
        project_id=str(project_id),
        file_schema_id=file_schema_id,
        field_name=field_name,
        removed=len(rule_ids),
    )
