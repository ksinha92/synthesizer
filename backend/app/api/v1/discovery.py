"""Discovery API endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.discovery.commands import (
    OverridePIIClassificationCommand,
    RunDiscoveryCommand,
)
from app.application.discovery.handlers import (
    GetDiscoveryResultsHandler,
    GetPIIClassificationsHandler,
    GetRelationshipsHandler,
    OverridePIIHandler,
    RunDiscoveryHandler,
)
from app.application.discovery.queries import (
    GetDiscoveryResultsQuery,
    GetPIIClassificationsQuery,
    GetRelationshipsQuery,
)
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.discovery_repo import SQLAlchemyDiscoveryRepository

logger = structlog.get_logger()

router = APIRouter(
    prefix="/projects/{project_id}/discovery",
    tags=["discovery"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


# --- Request/Response Models ---


class RunDiscoveryRequest(BaseModel):
    connection_id: str


class RunDiscoveryResponse(BaseModel):
    job_id: str
    status: str = "pending"


class OverrideClassificationRequest(BaseModel):
    pii_type: str
    classification: str = "manually_classified"
    note: str = ""


class PIIColumnResponse(BaseModel):
    id: str
    table_id: str
    column_name: str
    data_type: str
    pii_type: str
    confidence: float
    detector: str
    classification: str
    override_by: str | None
    override_note: str | None


# --- Endpoints ---


@router.post("/run", response_model=RunDiscoveryResponse, status_code=202)
async def run_discovery(
    project_id: uuid.UUID,
    body: RunDiscoveryRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Trigger async schema discovery + PII detection."""
    repo = SQLAlchemyDiscoveryRepository(session)
    handler = RunDiscoveryHandler(repo, None, session)

    command = RunDiscoveryCommand(
        connection_id=uuid.UUID(body.connection_id),
        project_id=project_id,
        user_id=uuid.UUID(current_user["id"]),
    )

    job_id = await handler.handle(command)

    await logger.ainfo(
        "discovery_run_triggered",
        project_id=str(project_id),
        connection_id=body.connection_id,
        user_id=current_user["id"],
        ip=request.client.host if request.client else "unknown",
    )

    return RunDiscoveryResponse(job_id=str(job_id))


@router.get("/results")
async def get_discovery_results(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Get schema tree (schemas → tables → columns)."""
    repo = SQLAlchemyDiscoveryRepository(session)
    handler = GetDiscoveryResultsHandler(repo)

    results = await handler.handle(GetDiscoveryResultsQuery(connection_id=connection_id))

    # Serialize schema tree
    tree = []
    for item in results:
        schema = item["schema"]
        tables = []
        for t_item in item["tables"]:
            table = t_item["table"]
            columns = [
                {
                    "id": str(c.id),
                    "column_name": c.column_name,
                    "data_type": c.data_type,
                    "is_nullable": c.is_nullable,
                    "is_primary_key": c.is_primary_key,
                    "is_foreign_key": c.is_foreign_key,
                    "pii_type": c.pii_type.value,
                    "pii_confidence": c.pii_confidence.score,
                    "classification": c.classification.value,
                    "stats": c.stats,
                }
                for c in t_item["columns"]
            ]
            tables.append({
                "id": str(table.id),
                "table_name": table.table_name,
                "row_count": table.row_count,
                "size_bytes": table.size_bytes,
                "columns": columns,
            })
        tree.append({
            "id": str(schema.id),
            "schema_name": schema.schema_name,
            "discovered_at": schema.discovered_at.isoformat(),
            "tables": tables,
        })

    return {"schemas": tree}


@router.get("/pii")
async def get_pii_classifications(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    min_confidence: float = 0.0,
    pii_type: str | None = None,
    classification: str | None = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Get PII classifications with filters."""
    repo = SQLAlchemyDiscoveryRepository(session)
    handler = GetPIIClassificationsHandler(repo)

    columns = await handler.handle(
        GetPIIClassificationsQuery(
            schema_id=schema_id,
            min_confidence=min_confidence,
            pii_type=pii_type,
            classification=classification,
        )
    )

    return {
        "columns": [
            PIIColumnResponse(
                id=str(c.id),
                table_id=str(c.table_id),
                column_name=c.column_name,
                data_type=c.data_type,
                pii_type=c.pii_type.value,
                confidence=c.pii_confidence.score,
                detector=c.pii_confidence.detector,
                classification=c.classification.value,
                override_by=str(c.override_by) if c.override_by else None,
                override_note=c.override_note,
            ).model_dump()
            for c in columns
        ],
        "total_count": len(columns),
    }


@router.put("/columns/{column_id}/classification")
async def override_classification(
    project_id: uuid.UUID,
    column_id: uuid.UUID,
    body: OverrideClassificationRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Override PII classification for a column."""
    repo = SQLAlchemyDiscoveryRepository(session)
    handler = OverridePIIHandler(repo)

    command = OverridePIIClassificationCommand(
        column_id=column_id,
        pii_type=body.pii_type,
        classification=body.classification,
        user_id=uuid.UUID(current_user["id"]),
        note=body.note,
    )

    column = await handler.handle(command)

    await logger.ainfo(
        "pii_classification_overridden",
        column_id=str(column_id),
        project_id=str(project_id),
        pii_type=body.pii_type,
        user_id=current_user["id"],
        ip=request.client.host if request.client else "unknown",
    )

    return {"status": "updated", "column_id": str(column_id), "pii_type": body.pii_type}


@router.get("/relationships")
async def get_relationships(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Get inferred relationships."""
    repo = SQLAlchemyDiscoveryRepository(session)
    handler = GetRelationshipsHandler(repo)

    relationships = await handler.handle(GetRelationshipsQuery(schema_id=schema_id))

    return {
        "relationships": [
            {
                "id": str(r.id),
                "source_table_id": str(r.source_table_id),
                "source_column_id": str(r.source_column_id),
                "target_table_id": str(r.target_table_id),
                "target_column_id": str(r.target_column_id),
                "relationship_type": r.relationship_type.value,
                "confidence": r.confidence,
                "is_virtual": r.is_virtual,
            }
            for r in relationships
        ]
    }
