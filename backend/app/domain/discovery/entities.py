"""Discovery domain entities. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.shared.entity import AggregateRoot, Entity
from app.domain.discovery.value_objects import (
    Classification,
    PIIConfidence,
    PIIType,
    RelationshipType,
)


@dataclass
class DiscoveredSchema(AggregateRoot):
    """A discovered database schema."""

    connection_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    schema_name: str = ""
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiscoveredTable(Entity):
    """A discovered table within a schema."""

    schema_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    table_name: str = ""
    row_count: int = 0
    size_bytes: int = 0


@dataclass
class DiscoveredColumn(Entity):
    """A discovered column with PII classification."""

    table_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    column_name: str = ""
    data_type: str = ""
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    fk_references: dict | None = None
    sample_values: list = field(default_factory=list)  # Masked before storage
    stats: dict = field(default_factory=dict)  # cardinality, null_percentage, min, max
    pii_type: PIIType = PIIType.NONE
    pii_confidence: PIIConfidence = field(default_factory=PIIConfidence)
    classification: Classification = Classification.NEEDS_REVIEW
    override_by: uuid.UUID | None = None
    override_note: str | None = None


@dataclass
class DiscoveredRelationship(Entity):
    """An inferred or declared relationship between columns."""

    schema_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    source_table_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    source_column_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    target_table_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    target_column_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    relationship_type: RelationshipType = RelationshipType.FOREIGN_KEY
    confidence: float = 1.0
    is_virtual: bool = False
