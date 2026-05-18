"""Cross-file FK suggestion endpoint.

Returns a ranked list of candidate relationships across every pair of
file schemas in the project. The UI presents these with per-row evidence
chips and a confidence-threshold slider; the user accepts the ones they
trust, which then persist into ``FileSetDefinition.foreign_keys``.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.synthetic.file_schema import FileSchemaDefinition
from app.domain.synthetic.relationship_suggester import (
    DEFAULT_MIN_SCORE,
    RelationshipSuggestion,
    suggest_relationships,
)
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.file_schema_repo import (
    SQLAlchemyFileSchemaRepository,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/projects/{project_id}/file-schemas",
    tags=["file-schema-relationships"],
)


class RelationshipEvidenceResponse(BaseModel):
    name_similarity: float
    type_compatibility: float
    cardinality_match: bool
    value_overlap: float | None


class RelationshipSuggestionResponse(BaseModel):
    source_file: str
    source_field: str
    target_file: str
    target_field: str
    score: float
    evidence: RelationshipEvidenceResponse
    sample_size: int


class SuggestRelationshipsResponse(BaseModel):
    suggestions: list[RelationshipSuggestionResponse]
    schemas_considered: int
    threshold: float


def _to_response(s: RelationshipSuggestion) -> RelationshipSuggestionResponse:
    return RelationshipSuggestionResponse(
        source_file=s.source_file,
        source_field=s.source_field,
        target_file=s.target_file,
        target_field=s.target_field,
        score=s.score,
        evidence=RelationshipEvidenceResponse(
            name_similarity=s.evidence.name_similarity,
            type_compatibility=s.evidence.type_compatibility,
            cardinality_match=s.evidence.cardinality_match,
            value_overlap=s.evidence.value_overlap,
        ),
        sample_size=s.sample_size,
    )


@router.get(
    "/suggest-relationships",
    response_model=SuggestRelationshipsResponse,
)
async def get_relationship_suggestions(
    project_id: uuid.UUID,
    min_score: float = Query(
        DEFAULT_MIN_SCORE,
        ge=0.0,
        le=1.0,
        description="Floor for returned suggestions (0..1).",
    ),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Rank cross-file FK candidates across every pair of file schemas."""
    repo = SQLAlchemyFileSchemaRepository(session)
    raw_schemas = await repo.list_by_project(project_id)
    if len(raw_schemas) < 2:
        return SuggestRelationshipsResponse(
            suggestions=[], schemas_considered=len(raw_schemas), threshold=min_score
        )

    try:
        schemas = [FileSchemaDefinition.from_dict(s) for s in raw_schemas]
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            500,
            {"error": "schema_decode_failed", "detail": str(exc)},
        )

    suggestions = suggest_relationships(schemas, min_score=min_score)
    await logger.ainfo(
        "file_schema_relationships_suggested",
        project_id=str(project_id),
        schema_count=len(schemas),
        suggestion_count=len(suggestions),
        min_score=min_score,
    )
    return SuggestRelationshipsResponse(
        suggestions=[_to_response(s) for s in suggestions],
        schemas_considered=len(schemas),
        threshold=min_score,
    )
