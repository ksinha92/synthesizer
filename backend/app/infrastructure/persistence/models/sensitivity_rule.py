"""Sensitivity rule ORM model (Phase 52, migration 018)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SensitivityRuleModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sensitivity_rules"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    match_type: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_pii_type: Mapped[str] = mapped_column(String(50), nullable=False)
    suggested_preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generator_presets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
