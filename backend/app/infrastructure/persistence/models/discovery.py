"""Discovery ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DiscoveredSchemaModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovered_schemas"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connections.id"), nullable=False, index=True
    )
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DiscoveredTableModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovered_tables"

    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovered_schemas.id"), nullable=False, index=True
    )
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)


class DiscoveredColumnModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovered_columns"

    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovered_tables.id"), nullable=False, index=True
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False)
    fk_references: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sample_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pii_type: Mapped[str] = mapped_column(String(50), default="none", index=True)
    pii_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    classification: Mapped[str] = mapped_column(String(50), default="needs_review")
    override_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    override_note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DiscoveredRelationshipModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovered_relationships"

    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovered_schemas.id"), nullable=False, index=True
    )
    source_table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_column_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_column_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    # Phase 54: user-asserted virtual FK vs discovered relationship.
    is_virtual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
