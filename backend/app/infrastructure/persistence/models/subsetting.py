"""Subsetting ORM models."""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubsetConfigModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subset_configs"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_connection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("connections.id", ondelete="SET NULL"), nullable=True)
    target_connection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    root_tables: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    traversal_strategy: Mapped[str] = mapped_column(String(50), default="upstream")
    # Phase 54: where subset output should land.
    output_mode: Mapped[str] = mapped_column(
        String(50), nullable=False, default="same_database", server_default="same_database"
    )
