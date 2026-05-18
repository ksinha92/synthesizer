"""Data dictionary mapper — derive a new file schema from an existing one.

Models the Altova MapForce / Talend Data Mapper pattern: pick source
fields, map each one to a target field, optionally apply lightweight
transforms (trim, pad, upper/lower, substring, date_format), and persist
the result as a brand-new FileSchemaDefinition. ``metadata.derived_from``
+ ``metadata.mappings`` preserve enough information for the mapping to
be re-loaded into the dictionary mapper modal and edited.
"""

from __future__ import annotations

import math
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.synthetic.file_schema import (
    FileFieldDefinition,
    FileSchemaDefinition,
)
from app.domain.synthetic.value_objects import CompType
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.file_schema_repo import (
    SQLAlchemyFileSchemaRepository,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/projects/{project_id}/file-schemas",
    tags=["file-schema-mapper"],
)


_ALLOWED_TRANSFORMS = {"trim", "pad", "upper", "lower", "substring", "date_format"}


class TransformSpec(BaseModel):
    type: str
    args: dict[str, Any] = Field(default_factory=dict)


class MappingSpec(BaseModel):
    target_field: str = Field(..., min_length=1, max_length=255)
    source_field: str | None = None  # None when target is filled by a constant only
    constant: str | None = None  # ignored when source_field is set
    transforms: list[TransformSpec] = Field(default_factory=list)


class DeriveSchemaRequest(BaseModel):
    target_name: str = Field(..., min_length=1, max_length=255)
    target_format: str = "csv"
    target_encoding: str = "utf8"
    mappings: list[MappingSpec] = Field(..., min_length=1)
    target_output_filename: str | None = None


def _validate_transforms(mappings: list[MappingSpec]) -> None:
    for m in mappings:
        for t in m.transforms:
            if t.type not in _ALLOWED_TRANSFORMS:
                raise HTTPException(
                    400,
                    {
                        "error": "invalid_transform",
                        "detail": f"transform.type must be one of {sorted(_ALLOWED_TRANSFORMS)}",
                    },
                )
            if t.type == "pad":
                length = t.args.get("length")
                if not isinstance(length, int) or length <= 0:
                    raise HTTPException(
                        400,
                        {
                            "error": "invalid_transform_args",
                            "detail": "pad requires a positive integer 'length'",
                        },
                    )
            elif t.type == "substring":
                start = t.args.get("start", 0)
                if not isinstance(start, int) or start < 0:
                    raise HTTPException(
                        400,
                        {
                            "error": "invalid_transform_args",
                            "detail": "substring requires a non-negative integer 'start'",
                        },
                    )


def _derive_target_field(
    source_field: FileFieldDefinition | None,
    mapping: MappingSpec,
    current_position: int,
) -> FileFieldDefinition:
    """Build a target FileFieldDefinition by inheriting from the source.

    When ``source_field`` is None, the target is a constant column with
    ``length`` taken from the constant value (or 1 byte minimum).
    """
    if source_field is None:
        const_len = max(1, len(mapping.constant or ""))
        return FileFieldDefinition(
            name=mapping.target_field,
            data_type="alphanumeric",
            length=const_len,
            byte_length=const_len,
            start_position=current_position,
            decimal_places=0,
            comp_type=CompType.NONE.value,
            nullable=False,
            pii_type=None,
            fk_reference=None,
        )

    # Inherit type metadata from the source; apply transforms that change
    # length (substring, pad) when present so the target byte_length
    # reflects post-transform width.
    length = source_field.length
    byte_length = source_field.byte_length
    for t in mapping.transforms:
        if t.type == "pad":
            length = int(t.args["length"])
            byte_length = length
        elif t.type == "substring":
            start = int(t.args.get("start", 0))
            end = t.args.get("end")
            if end is None:
                length = max(0, length - start)
            else:
                length = max(0, int(end) - start)
            byte_length = length

    return FileFieldDefinition(
        name=mapping.target_field,
        data_type=source_field.data_type,
        length=length,
        byte_length=byte_length,
        start_position=current_position,
        decimal_places=source_field.decimal_places,
        signed=source_field.signed,
        comp_type=source_field.comp_type,
        nullable=source_field.nullable,
        pii_type=source_field.pii_type,
        fk_reference=None,
        is_filler=False,
    )


def _build_target_fields(
    body: DeriveSchemaRequest, source_by_name: dict[str, FileFieldDefinition]
) -> list[FileFieldDefinition]:
    """Validate the mapping payload + materialize the target field list.

    Shared by both ``POST /derive`` (create) and ``PATCH /mapping``
    (re-edit) so a future tweak to validation rules or field-derivation
    logic ships to both code paths at once. Raises HTTPException on
    malformed input — caller does not need to re-validate.
    """
    target_fields: list[FileFieldDefinition] = []
    cursor = 0
    seen_target_names: set[str] = set()
    for m in body.mappings:
        if m.target_field in seen_target_names:
            raise HTTPException(
                400,
                {
                    "error": "duplicate_target_field",
                    "detail": f"target_field '{m.target_field}' appears twice",
                },
            )
        seen_target_names.add(m.target_field)
        source_field: FileFieldDefinition | None = None
        if m.source_field:
            source_field = source_by_name.get(m.source_field)
            if source_field is None:
                raise HTTPException(
                    400,
                    {
                        "error": "unknown_source_field",
                        "detail": f"source_field '{m.source_field}' not in source schema",
                    },
                )
        target = _derive_target_field(source_field, m, cursor)
        target_fields.append(target)
        cursor += target.byte_length
    return target_fields


@router.post("/{schema_id}/derive", status_code=201)
async def derive_schema(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    body: DeriveSchemaRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Derive a new file schema from an existing one via field mapping."""
    _validate_transforms(body.mappings)

    repo = SQLAlchemyFileSchemaRepository(session)
    source_dict = await repo.get(schema_id)
    if not source_dict or source_dict.get("project_id") != str(project_id):
        raise HTTPException(
            404, {"error": "not_found", "detail": "Source schema not in this project"}
        )
    source_schema = FileSchemaDefinition.from_dict(source_dict)
    source_by_name = {f.name: f for f in source_schema.fields}

    target_fields = _build_target_fields(body, source_by_name)
    record_length = sum(f.byte_length for f in target_fields)

    target_schema = FileSchemaDefinition(
        name=body.target_name,
        fields=target_fields,
        file_format=body.target_format,
        encoding=body.target_encoding,
        record_length=record_length,
        output_filename=body.target_output_filename,
        metadata={
            "derived_from": str(schema_id),
            "derived_from_name": source_schema.name,
            # Persist the mapping list so the dictionary mapper modal can
            # re-hydrate the same mapping for further edits.
            "mappings": [m.model_dump() for m in body.mappings],
        },
    )

    save_dict = {
        "project_id": project_id,
        "name": target_schema.name,
        "file_format": target_schema.file_format,
        "encoding": target_schema.encoding,
        "record_length": target_schema.record_length,
        "has_rdw": False,
        "output_filename": target_schema.output_filename,
        "fields": [f.to_dict() for f in target_schema.fields],
        "metadata": target_schema.metadata,
        "layout_variants": [],
    }
    saved = await repo.save(save_dict)
    await logger.ainfo(
        "file_schema_derived",
        source_id=str(schema_id),
        new_id=saved["id"],
        project_id=str(project_id),
        mapping_count=len(body.mappings),
    )
    return {
        "id": saved["id"],
        "name": saved["name"],
        "field_count": len(target_fields),
        "record_length": record_length,
        "derived_from": str(schema_id),
    }


@router.patch("/{schema_id}/mapping", status_code=200)
async def update_derived_schema(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    body: DeriveSchemaRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Re-edit an existing derived schema in place.

    The Files → Mappings tab's "Re-edit" button hits this so an analyst
    who tweaks a mapping doesn't end up with a second derived schema —
    the original row is updated, all rules / file-set wiring that
    references its id stay intact. The source schema referenced by the
    original ``metadata.derived_from`` cannot be swapped here; callers
    that want a different source should ``POST /derive`` for a new
    schema instead.
    """
    _validate_transforms(body.mappings)

    repo = SQLAlchemyFileSchemaRepository(session)
    existing = await repo.get(schema_id)
    if not existing or existing.get("project_id") != str(project_id):
        raise HTTPException(
            404, {"error": "not_found", "detail": "Schema not in this project"}
        )

    metadata = existing.get("metadata") or {}
    source_id_str = metadata.get("derived_from")
    if not source_id_str:
        raise HTTPException(
            400,
            {
                "error": "not_derived",
                "detail": "Schema was not produced by the dictionary mapper",
            },
        )
    try:
        source_uuid = uuid.UUID(source_id_str)
    except ValueError:
        raise HTTPException(
            500,
            {
                "error": "corrupt_metadata",
                "detail": "Stored derived_from is not a UUID",
            },
        )

    source_dict = await repo.get(source_uuid)
    if not source_dict:
        raise HTTPException(
            404,
            {
                "error": "source_gone",
                "detail": "Source schema no longer exists",
            },
        )
    source_schema = FileSchemaDefinition.from_dict(source_dict)
    source_by_name = {f.name: f for f in source_schema.fields}

    target_fields = _build_target_fields(body, source_by_name)
    record_length = sum(f.byte_length for f in target_fields)

    save_dict = {
        # ``id`` preserved → SQLAlchemyFileSchemaRepository.save updates
        # the existing row rather than inserting a new one.
        "id": schema_id,
        "project_id": project_id,
        "name": body.target_name,
        "file_format": body.target_format,
        "encoding": body.target_encoding,
        "record_length": record_length,
        "has_rdw": False,
        "output_filename": body.target_output_filename,
        "fields": [f.to_dict() for f in target_fields],
        "metadata": {
            "derived_from": source_id_str,
            "derived_from_name": source_schema.name,
            "mappings": [m.model_dump() for m in body.mappings],
        },
        "layout_variants": [],
    }
    saved = await repo.save(save_dict)
    await logger.ainfo(
        "file_schema_derived_updated",
        derived_id=str(schema_id),
        source_id=source_id_str,
        project_id=str(project_id),
        mapping_count=len(body.mappings),
    )
    return {
        "id": saved["id"],
        "name": saved["name"],
        "field_count": len(target_fields),
        "record_length": record_length,
        "derived_from": source_id_str,
    }


@router.get("/{schema_id}/mappings")
async def get_existing_mappings(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Return persisted mapping spec for a derived schema (for re-edit).

    Schemas not derived via the mapper return ``derived_from = None``
    and an empty mapping list — the response shape is stable so the
    frontend can blanket-call this when opening the mapper modal.
    Target name/format/encoding are echoed back from the schema row so
    the modal can hydrate its state from a single network round-trip.
    """
    repo = SQLAlchemyFileSchemaRepository(session)
    schema = await repo.get(schema_id)
    if not schema or schema.get("project_id") != str(project_id):
        raise HTTPException(
            404, {"error": "not_found", "detail": "Schema not in this project"}
        )
    metadata = schema.get("metadata") or {}
    return {
        "derived_from": metadata.get("derived_from"),
        "derived_from_name": metadata.get("derived_from_name"),
        "mappings": metadata.get("mappings") or [],
        "target_name": schema.get("name"),
        "target_format": schema.get("file_format"),
        "target_encoding": schema.get("encoding"),
        "target_output_filename": schema.get("output_filename"),
    }
