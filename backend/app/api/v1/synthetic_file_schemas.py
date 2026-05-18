"""Synthetic file-schema and file-set endpoints.

Split out of ``synthetic.py`` in Phase 61 (F19) so the parent module stays
under the 500-LOC readability threshold. URL paths are preserved exactly —
this router is mounted under the same ``/projects/{project_id}/synthetic``
prefix in ``app/api/v1/__init__.py``.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import CompType, EncodingType, FileFormat
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.parsers.copybook_parser import CopybookParser
from app.infrastructure.parsers.excel_dictionary_parser import ExcelDictionaryParser
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.file_schema_repo import SQLAlchemyFileSchemaRepository

logger = structlog.get_logger()

router = APIRouter(
    prefix="/projects/{project_id}/synthetic",
    tags=["synthetic"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


# --- File Schema Request/Response Models ---


class FileFieldResponse(BaseModel):
    name: str
    data_type: str
    length: int
    byte_length: int
    start_position: int
    decimal_places: int = 0
    comp_type: str = "none"
    nullable: bool = True
    pii_type: str | None = None
    fk_reference: dict | None = None


class FileSchemaResponse(BaseModel):
    id: str
    name: str
    file_format: str
    encoding: str
    record_length: int
    field_count: int
    output_filename: str | None = None
    created_at: str | None = None


class LayoutConditionResponse(BaseModel):
    field_name: str
    operator: str  # "eq" | "ne" | "in" | "starts_with"
    value: str | list[str]


class LayoutVariantResponse(BaseModel):
    name: str
    fields: list[FileFieldResponse]
    conditions: list[LayoutConditionResponse]


class FileSchemaDetailResponse(FileSchemaResponse):
    fields: list[FileFieldResponse]
    has_rdw: bool = False
    metadata: dict | None = None
    layout_variants: list[LayoutVariantResponse] = []


class ManualFieldRequest(BaseModel):
    name: str
    data_type: str
    length: int
    decimal_places: int = 0
    comp_type: str = "none"
    nullable: bool = True
    pii_type: str | None = None
    fk_reference: str | None = None  # "file.field" format


class ManualSchemaRequest(BaseModel):
    name: str
    file_format: str = "csv"
    encoding: str = "utf8"
    fields: list[ManualFieldRequest]
    output_filename: str | None = None


class DiscoverySchemaRequest(BaseModel):
    table_name: str
    connection_id: str
    target_format: str = "csv"
    target_encoding: str = "utf8"


# --- Helpers ---


def _fields_to_responses(fields_data: list[dict]) -> list[FileFieldResponse]:
    out: list[FileFieldResponse] = []
    for f in fields_data:
        fk = f.get("fk_reference")
        out.append(FileFieldResponse(
            name=f["name"],
            data_type=f["data_type"],
            length=f["length"],
            byte_length=f["byte_length"],
            start_position=f["start_position"],
            decimal_places=f.get("decimal_places", 0),
            comp_type=f.get("comp_type", "none"),
            nullable=f.get("nullable", True),
            pii_type=f.get("pii_type"),
            fk_reference=fk if isinstance(fk, dict) else None,
        ))
    return out


def _variants_to_responses(variants_data: list[dict]) -> list[LayoutVariantResponse]:
    out: list[LayoutVariantResponse] = []
    for v in variants_data or []:
        conds = [
            LayoutConditionResponse(
                field_name=c["field_name"],
                operator=c["operator"],
                value=c["value"],
            )
            for c in v.get("conditions", [])
        ]
        out.append(
            LayoutVariantResponse(
                name=v.get("name") or "Layout",
                fields=_fields_to_responses(v.get("fields", [])),
                conditions=conds,
            )
        )
    return out


def _schema_dict_to_detail_response(data: dict) -> FileSchemaDetailResponse:
    """Convert a persisted schema dict to a detail response."""
    fields_data = data.get("fields", [])
    field_responses = _fields_to_responses(fields_data)
    variant_responses = _variants_to_responses(data.get("layout_variants") or [])

    return FileSchemaDetailResponse(
        id=data["id"],
        name=data["name"],
        file_format=data["file_format"],
        encoding=data["encoding"],
        record_length=data.get("record_length", 0),
        field_count=len(fields_data),
        output_filename=data.get("output_filename"),
        has_rdw=data.get("has_rdw", False),
        metadata=data.get("metadata"),
        created_at=data.get("created_at"),
        fields=field_responses,
        layout_variants=variant_responses,
    )


def _schema_definition_to_save_dict(
    schema: FileSchemaDefinition, project_id: uuid.UUID
) -> dict:
    """Convert a FileSchemaDefinition to a dict ready for repository save."""
    return {
        "project_id": project_id,
        "name": schema.name,
        "file_format": schema.file_format,
        "encoding": schema.encoding,
        "record_length": schema.record_length,
        "has_rdw": schema.has_rdw,
        "output_filename": schema.output_filename,
        "fields": [f.to_dict() for f in schema.fields],
        "metadata": schema.metadata,
        "layout_variants": [v.to_dict() for v in schema.layout_variants],
    }


# --- File Schema Endpoints ---


@router.post("/file-schemas/upload-copybook", response_model=FileSchemaDetailResponse, status_code=201)
async def upload_copybook(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    split_strategy: str = Query(
        "single",
        description="single | split_01 | split_redefine — how to handle multi-record copybooks",
    ),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Upload a COBOL copybook and parse it into a file schema."""
    content = await file.read()
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception as exc:
        await logger.awarning(
            "copybook_decode_failed",
            filename=file.filename,
            error=type(exc).__name__,
            project_id=str(project_id),
        )
        raise HTTPException(400, {"error": "invalid_file", "detail": "Could not decode copybook file"})

    from app.infrastructure.parsers.copybook_parser import SplitStrategy

    try:
        strategy = SplitStrategy(split_strategy)
    except ValueError:
        raise HTTPException(
            400,
            {
                "error": "invalid_split_strategy",
                "detail": "split_strategy must be one of: single, split_01, split_redefine",
            },
        )

    parser = CopybookParser()
    try:
        schema = parser.parse(
            text, name=file.filename or "copybook", split_strategy=strategy
        )
    except ValueError as e:
        raise HTTPException(422, {"error": "parse_error", "detail": str(e)})

    repo = SQLAlchemyFileSchemaRepository(session)
    save_dict = _schema_definition_to_save_dict(schema, project_id)
    saved = await repo.save(save_dict)

    await logger.ainfo(
        "file_schema_created",
        source="copybook",
        schema_id=saved["id"],
        project_id=str(project_id),
        user_id=current_user["id"],
    )

    return _schema_dict_to_detail_response(saved)


@router.post("/file-schemas/upload-dictionary", response_model=FileSchemaDetailResponse, status_code=201)
async def upload_dictionary(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    target_format: str = Query("csv", description="Target file format"),
    target_encoding: str = Query("utf8", description="Target encoding"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Upload an Excel data dictionary (.xlsx) and parse it into a file schema."""
    content = await file.read()

    # Validate format/encoding enums
    try:
        fmt = FileFormat(target_format)
    except ValueError:
        raise HTTPException(422, {"error": "invalid_format", "detail": f"Invalid format: {target_format}"})
    try:
        enc = EncodingType(target_encoding)
    except ValueError:
        raise HTTPException(422, {"error": "invalid_encoding", "detail": f"Invalid encoding: {target_encoding}"})

    parser = ExcelDictionaryParser()
    try:
        schema = parser.parse(content, name=file.filename or "dictionary", target_format=fmt, target_encoding=enc)
    except ValueError as e:
        raise HTTPException(422, {"error": "parse_error", "detail": str(e)})

    repo = SQLAlchemyFileSchemaRepository(session)
    save_dict = _schema_definition_to_save_dict(schema, project_id)
    saved = await repo.save(save_dict)

    await logger.ainfo(
        "file_schema_created",
        source="excel_dictionary",
        schema_id=saved["id"],
        project_id=str(project_id),
        user_id=current_user["id"],
    )

    return _schema_dict_to_detail_response(saved)


@router.post("/file-schemas/manual", response_model=FileSchemaDetailResponse, status_code=201)
async def create_manual_schema(
    project_id: uuid.UUID,
    body: ManualSchemaRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Create a file schema from manually defined field definitions."""
    import math

    # Build FileSchemaDefinition from request
    fields: list[FileFieldDefinition] = []
    current_pos = 0

    for f in body.fields:
        # Compute byte_length
        comp = f.comp_type.lower()
        length = f.length
        if comp == CompType.COMP_3.value:
            byte_length = math.ceil((length + 1) / 2)
        elif comp == CompType.COMP.value:
            byte_length = 2 if length <= 4 else (4 if length <= 9 else 8)
        else:
            byte_length = length

        # Parse fk_reference
        fk_ref = None
        if f.fk_reference and "." in f.fk_reference:
            parts = f.fk_reference.split(".", 1)
            fk_ref = (parts[0], parts[1])

        field_def = FileFieldDefinition(
            name=f.name,
            data_type=f.data_type,
            length=length,
            byte_length=byte_length,
            start_position=current_pos,
            decimal_places=f.decimal_places,
            comp_type=comp,
            nullable=f.nullable,
            pii_type=f.pii_type,
            fk_reference=fk_ref,
        )
        fields.append(field_def)
        current_pos += byte_length

    schema = FileSchemaDefinition(
        name=body.name,
        fields=fields,
        file_format=body.file_format,
        encoding=body.encoding,
        record_length=sum(f.byte_length for f in fields),
        output_filename=body.output_filename,
    )

    errors = schema.validate()
    if errors:
        # Filter out warnings
        real_errors = [e for e in errors if not e.startswith("Warning:")]
        if real_errors:
            raise HTTPException(422, {"error": "validation_error", "detail": real_errors})

    repo = SQLAlchemyFileSchemaRepository(session)
    save_dict = _schema_definition_to_save_dict(schema, project_id)
    saved = await repo.save(save_dict)

    await logger.ainfo(
        "file_schema_created",
        source="manual",
        schema_id=saved["id"],
        project_id=str(project_id),
        user_id=current_user["id"],
    )

    return _schema_dict_to_detail_response(saved)


@router.post("/file-schemas/from-discovery", response_model=FileSchemaDetailResponse, status_code=201)
async def create_from_discovery(
    project_id: uuid.UUID,
    body: DiscoverySchemaRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Create a file schema from existing discovery metadata."""
    from sqlalchemy import select as sa_select
    from app.infrastructure.persistence.models.discovery import (
        DiscoveredColumnModel,
        DiscoveredSchemaModel,
        DiscoveredTableModel,
    )

    # Find the connection to get its discovered schema
    conn_result = await session.execute(
        sa_select(DiscoveredSchemaModel).where(
            DiscoveredSchemaModel.connection_id == uuid.UUID(body.connection_id)
        )
    )
    schema_model = conn_result.scalar_one_or_none()
    if not schema_model:
        raise HTTPException(404, {
            "error": "not_found",
            "detail": f"No discovery results found for connection '{body.connection_id}'",
        })

    # Find the table
    table_result = await session.execute(
        sa_select(DiscoveredTableModel).where(
            DiscoveredTableModel.schema_id == schema_model.id,
            DiscoveredTableModel.table_name == body.table_name,
        ).limit(1)
    )
    table_model = table_result.scalar_one_or_none()
    if not table_model:
        raise HTTPException(404, {
            "error": "not_found",
            "detail": f"No discovery results found for table '{body.table_name}'",
        })

    # Load columns
    col_result = await session.execute(
        sa_select(DiscoveredColumnModel).where(
            DiscoveredColumnModel.table_id == table_model.id,
        )
    )
    columns = col_result.scalars().all()

    sql_type_map = {
        "varchar": "alphanumeric", "char": "alphanumeric", "text": "alphanumeric",
        "nvarchar": "alphanumeric", "nchar": "alphanumeric",
        "int": "numeric", "integer": "numeric", "bigint": "numeric",
        "smallint": "numeric", "tinyint": "numeric",
        "decimal": "decimal", "numeric": "decimal", "float": "decimal",
        "double": "decimal", "real": "decimal", "money": "decimal",
        "binary": "binary", "varbinary": "binary", "blob": "binary",
    }

    fields: list[FileFieldDefinition] = []
    current_pos = 0

    for col in columns:
        col_type = col.data_type.lower().split("(")[0].strip() if col.data_type else "varchar"
        # Extract length from stats or default
        col_stats = col.stats or {}
        col_length = col_stats.get("max_length") or col_stats.get("character_maximum_length") or 20

        try:
            col_length = int(col_length)
        except (TypeError, ValueError):
            col_length = 20

        data_type = sql_type_map.get(col_type, "alphanumeric")
        pii_type = col.pii_type if col.pii_type and col.pii_type != "none" else None

        field_def = FileFieldDefinition(
            name=col.column_name,
            data_type=data_type,
            length=col_length,
            byte_length=col_length,
            start_position=current_pos,
            nullable=col.is_nullable,
            pii_type=pii_type,
        )
        fields.append(field_def)
        current_pos += col_length

    if not fields:
        raise HTTPException(422, {
            "error": "no_columns",
            "detail": f"No columns found in discovery results for table '{body.table_name}'",
        })

    schema = FileSchemaDefinition(
        name=body.table_name,
        fields=fields,
        file_format=body.target_format,
        encoding=body.target_encoding,
        record_length=sum(f.byte_length for f in fields),
        metadata={"source_type": "discovery", "table_name": body.table_name, "connection_id": body.connection_id},
    )

    repo = SQLAlchemyFileSchemaRepository(session)
    save_dict = _schema_definition_to_save_dict(schema, project_id)
    saved = await repo.save(save_dict)

    await logger.ainfo(
        "file_schema_created",
        source="discovery",
        schema_id=saved["id"],
        project_id=str(project_id),
        table_name=body.table_name,
        user_id=current_user["id"],
    )

    return _schema_dict_to_detail_response(saved)


class LayoutConditionRequest(BaseModel):
    field_name: str
    operator: str  # "eq" | "ne" | "in" | "starts_with"
    value: str | list[str]


class LayoutVariantConditionsUpdate(BaseModel):
    variant_name: str
    conditions: list[LayoutConditionRequest]


class UpdateLayoutVariantsRequest(BaseModel):
    variants: list[LayoutVariantConditionsUpdate]


_ALLOWED_OPERATORS = {"eq", "ne", "in", "starts_with"}


@router.patch(
    "/file-schemas/{schema_id}/layout-variants",
    response_model=FileSchemaDetailResponse,
)
async def update_layout_variant_conditions(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    body: UpdateLayoutVariantsRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Apply discriminator conditions to a multi-record schema's layout variants.

    The copybook parser emits unconditional variants because it can't know
    which field selects which layout. After upload, the wizard collects
    those conditions from the user and posts them here. We replace each
    matching variant's ``conditions`` list while preserving everything else.
    """
    repo = SQLAlchemyFileSchemaRepository(session)
    existing = await repo.get(schema_id)
    if not existing or existing.get("project_id") != str(project_id):
        raise HTTPException(404, {"error": "not_found", "detail": "Schema not in this project"})

    variants_in: list[dict] = list(existing.get("layout_variants") or [])
    by_name = {v.get("name"): v for v in variants_in}

    for update in body.variants:
        target = by_name.get(update.variant_name)
        if target is None:
            raise HTTPException(
                404,
                {"error": "variant_not_found", "detail": f"No variant '{update.variant_name}'"},
            )
        for cond in update.conditions:
            if cond.operator not in _ALLOWED_OPERATORS:
                raise HTTPException(
                    400,
                    {
                        "error": "invalid_operator",
                        "detail": f"operator must be one of {sorted(_ALLOWED_OPERATORS)}",
                    },
                )
        target["conditions"] = [
            {"field_name": c.field_name, "operator": c.operator, "value": c.value}
            for c in update.conditions
        ]

    # Round-trip through the domain so the saved shape matches what
    # uploads produce. variants_in already carries the updated conditions
    # via the mutation above.
    from app.domain.synthetic.file_schema import LayoutVariant
    schema = FileSchemaDefinition.from_dict(existing)
    schema.layout_variants = [LayoutVariant.from_dict(v) for v in variants_in]

    save_dict = _schema_definition_to_save_dict(schema, project_id)
    save_dict["id"] = schema_id  # preserve the existing row
    saved = await repo.save(save_dict)
    await logger.ainfo(
        "file_schema_layout_variants_updated",
        schema_id=str(schema_id),
        project_id=str(project_id),
        variants_updated=len(body.variants),
    )
    return _schema_dict_to_detail_response(saved)


@router.get("/file-schemas/{schema_id}", response_model=FileSchemaDetailResponse)
async def get_file_schema(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Return the full detail (fields + layout variants) for one schema."""
    repo = SQLAlchemyFileSchemaRepository(session)
    schema = await repo.get(schema_id)
    if not schema or schema.get("project_id") != str(project_id):
        raise HTTPException(
            404, {"error": "not_found", "detail": "Schema not in this project"}
        )
    return _schema_dict_to_detail_response(schema)


@router.get("/file-schemas", response_model=list[FileSchemaResponse])
async def list_file_schemas(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """List all file schemas for a project."""
    repo = SQLAlchemyFileSchemaRepository(session)
    schemas = await repo.list_by_project(project_id)
    return [
        FileSchemaResponse(
            id=s["id"],
            name=s["name"],
            file_format=s["file_format"],
            encoding=s["encoding"],
            record_length=s.get("record_length", 0),
            field_count=len(s.get("fields", [])),
            output_filename=s.get("output_filename"),
            created_at=s.get("created_at"),
        )
        for s in schemas
    ]


# ── File-set download (Phase 46) ────────────────────────────────────────────


@router.get("/jobs/{job_id}/file-output")
async def download_file_output(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Stream the zip bundle produced by a completed file-set generation job."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    from sqlalchemy import select as sa_select

    from app.infrastructure.persistence.models.job import JobModel

    result = await session.execute(sa_select(JobModel).where(JobModel.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, {"error": "not_found", "detail": "Job not found"})
    if str(job.project_id) != str(project_id):
        raise HTTPException(404, {"error": "not_found", "detail": "Job not in this project"})
    # A run that completed with warnings (some masking rules skipped) still
    # produced a usable bundle — the file lives on disk and downstream
    # consumers may need it. The warning surfaces via job.status +
    # job.error_message + result_summary.masking_skipped, but it must NOT
    # block download.
    if job.status not in ("completed", "completed_with_warnings"):
        raise HTTPException(409, {"error": "not_ready", "detail": f"Job status={job.status}"})

    bundle_path = (job.result_summary or {}).get("bundle_path")
    if not bundle_path:
        raise HTTPException(404, {"error": "no_bundle", "detail": "Job did not produce a file bundle"})
    p = Path(bundle_path)
    if not p.exists():
        raise HTTPException(410, {"error": "bundle_missing", "detail": "Bundle was removed from storage"})

    return FileResponse(p, media_type="application/zip", filename=p.name)


# ── File-set generation launcher (Phase 47) ────────────────────────────────


class FileSetGenerateRequest(BaseModel):
    file_set: dict  # FileSetDefinition.to_dict() shape
    row_counts: dict[str, int] | None = None


@router.post("/file-sets/generate", status_code=202)
async def generate_file_set(
    project_id: uuid.UUID,
    body: FileSetGenerateRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Launch multi-file generation. Returns a job_id."""
    from app.domain.synthetic.file_schema import FileSetDefinition
    from app.infrastructure.messaging.synthetic_tasks import run_file_set_generation_task
    from app.infrastructure.persistence.models.job import JobModel

    file_set_dict = dict(body.file_set)
    if body.row_counts:
        file_set_dict["row_counts"] = body.row_counts

    try:
        file_set = FileSetDefinition.from_dict(file_set_dict)
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(400, {"error": "invalid_file_set", "detail": str(e)})

    # ``from_dict`` only proves the payload is structurally deserializable.
    # Run the domain ``validate()`` to catch typos in cross-file FK refs and
    # duplicate schema names *before* the worker silently generates the FK
    # column as ordinary random data.
    validation_errors = file_set.validate()
    if validation_errors:
        raise HTTPException(
            422,
            {
                "error": "invalid_file_set",
                "detail": "; ".join(validation_errors[:5]),
                "errors": validation_errors,
            },
        )

    job = JobModel(
        project_id=project_id,
        # Must match JobType.FILE_SET = "file_set"; the previous
        # "file_set_generation" string couldn't be hydrated by
        # JobRepository._to_entity and crashed every later jobs-API read.
        job_type="file_set",
        reference_id=project_id,
        status="pending",
        created_by=uuid.UUID(current_user["id"]),
    )
    session.add(job)
    await session.flush()

    run_file_set_generation_task.delay(file_set_dict, str(project_id), str(job.id))

    return {"job_id": str(job.id), "status": "pending"}
