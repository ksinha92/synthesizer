"""Compliance ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ComplianceReportModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "compliance_reports"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # hipaa | gdpr | ccpa
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Summary metadata only — full data in storage
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Phase 57 migration 022: marks pre-v0.9 rows that were produced while the
    # compliance handler hard-coded empty PII/masking lists. Backfilled to
    # ``true`` for every row that existed before the migration ran; new rows
    # default to ``false`` so they reflect the fixed code path.
    legacy: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
