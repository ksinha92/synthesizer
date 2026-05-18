"""Synthetic config ORM model."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SyntheticConfigModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "synthetic_configs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connections.id", ondelete="SET NULL"), nullable=True
    )
    target_connection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tables: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    generation_method: Mapped[str] = mapped_column(String(50), nullable=False, default="faker")
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    nlp_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    # Phase 54: where generated output should land.
    output_mode: Mapped[str] = mapped_column(
        String(50), nullable=False, default="same_database", server_default="same_database"
    )
