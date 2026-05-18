"""File data preview endpoint — the back end of the wizard's Step 3.

Takes a saved file schema plus a real data file uploaded by the user,
runs ``sample_file_parser`` to parse the first N records, and tags each
record with the matching LayoutVariant (if the schema is multi-record).

The uploaded data file is never persisted — it's parsed in a temp file
and discarded as soon as the response is built.
"""

from __future__ import annotations

import math
import tempfile
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.synthetic.file_schema import FileSchemaDefinition
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.parsers import sample_file_parser
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.file_schema_repo import (
    SQLAlchemyFileSchemaRepository,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/projects/{project_id}/file-schemas",
    tags=["file-schema-preview"],
)

# 50 MB cap — comfortably handles a synthetic test file without making this
# endpoint a vehicle for storage abuse. Larger inspections belong in the
# sandbox/ephemeral environment, not a synchronous REST call.
MAX_DATA_BYTES = 50 * 1024 * 1024
DEFAULT_PREVIEW_ROWS = 100
MAX_PREVIEW_ROWS = 1000


class PreviewFieldError(BaseModel):
    field: str
    row_index: int
    error: str


class PreviewRow(BaseModel):
    row_index: int
    layout: str  # "_base" when nothing matched
    fields: dict[str, Any]


class PreviewSummary(BaseModel):
    total_rows: int
    matched: dict[str, int]   # variant_name → count (includes "_base")
    parse_errors: int


class PreviewResponse(BaseModel):
    rows: list[PreviewRow]
    summary: PreviewSummary
    errors: list[PreviewFieldError]


@router.post("/{schema_id}/preview", response_model=PreviewResponse)
async def preview_file(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    file: UploadFile = File(...),
    limit: int = Form(DEFAULT_PREVIEW_ROWS),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Parse the first N records of an uploaded data file against a saved schema."""
    if limit < 1 or limit > MAX_PREVIEW_ROWS:
        raise HTTPException(
            400,
            {
                "error": "invalid_limit",
                "detail": f"limit must be 1..{MAX_PREVIEW_ROWS}",
            },
        )

    # Pull schema + ownership check before touching the upload stream.
    repo = SQLAlchemyFileSchemaRepository(session)
    stored = await repo.get(schema_id)
    if not stored or stored.get("project_id") != str(project_id):
        raise HTTPException(
            404, {"error": "not_found", "detail": "Schema not in this project"}
        )
    schema = FileSchemaDefinition.from_dict(stored)

    # Streaming size guard — we materialize the upload to a temp file
    # because pandas / VSAM reader work on file paths, not bytes.
    suffix = Path(file.filename or "").suffix or ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    bytes_seen = 0
    try:
        try:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_seen += len(chunk)
                if bytes_seen > MAX_DATA_BYTES:
                    raise HTTPException(
                        413,
                        {
                            "error": "file_too_large",
                            "detail": f"max {MAX_DATA_BYTES} bytes",
                        },
                    )
                tmp.write(chunk)
        finally:
            tmp.close()

        try:
            df = sample_file_parser.parse(Path(tmp.name), schema)
        except ValueError as exc:
            raise HTTPException(
                422, {"error": "parse_failed", "detail": str(exc)}
            )
        except Exception as exc:
            await logger.aexception(
                "preview_unexpected_failure",
                schema_id=str(schema_id),
                error=type(exc).__name__,
            )
            raise HTTPException(
                500, {"error": "internal", "detail": "Failed to parse file"}
            )

        # Trim to limit and convert rows to plain dicts for variant matching.
        df = df.head(limit)
        records = df.where(df.notnull(), None).to_dict(orient="records")

        # Variant matching pass — first matching variant wins; "_base"
        # is the fallback marker the UI uses for "no condition matched."
        matched_counts: dict[str, int] = {"_base": 0}
        for v in schema.layout_variants:
            matched_counts.setdefault(v.name, 0)

        out_rows: list[PreviewRow] = []
        errors: list[PreviewFieldError] = []
        for idx, raw in enumerate(records):
            # Coerce to JSON-safe primitives.
            normalized: dict[str, Any] = {}
            for k, v in raw.items():
                normalized[k] = _normalize(v)

            variant = schema.select_variant(normalized) if schema.layout_variants else None
            layout_name = variant.name if variant is not None else "_base"
            matched_counts[layout_name] = matched_counts.get(layout_name, 0) + 1
            out_rows.append(
                PreviewRow(row_index=idx, layout=layout_name, fields=normalized)
            )

        return PreviewResponse(
            rows=out_rows,
            summary=PreviewSummary(
                total_rows=len(records),
                matched=matched_counts,
                parse_errors=len(errors),
            ),
            errors=errors,
        )
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def _normalize(value: Any) -> Any:
    """Render numpy / pandas scalars into JSON-safe Python primitives."""
    if value is None:
        return None
    # pandas / numpy NaN check without pulling the import to the top.
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except TypeError:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value
