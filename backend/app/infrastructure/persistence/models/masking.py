"""Masking ORM models."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MaskingPolicyModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "masking_policies"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class MaskingRuleModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "masking_rules"

    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("masking_policies.id"), nullable=False, index=True)
    column_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    match_pattern: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    masking_type: Mapped[str] = mapped_column(String(50), nullable=False, default="redact")
    masking_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    preserve_format: Mapped[bool] = mapped_column(Boolean, default=False)
    deterministic: Mapped[bool] = mapped_column(Boolean, default=False)
    # Phase 51: optional reference to a global generator preset.
    # SET NULL on cascade — removing a preset unlinks rules but keeps them.
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generator_presets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Phase 53 (migration 019): linked-column joint generation + consistency group.
    linked_column_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    consistency_group: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
