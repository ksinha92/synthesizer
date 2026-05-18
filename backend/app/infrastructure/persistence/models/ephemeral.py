"""Ephemeral environment ORM model.

T3.1 (Tonic-parity). An ephemeral environment links a project to a
destination connection with an explicit TTL so dev teams can spin up
short-lived copies of synthesised data without long-term storage cost.
The data-copy controller is a follow-up — this model captures the
lifecycle so the UI + cleanup paths can work today.
"""

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.infrastructure.persistence.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class EphemeralEnvironmentModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ephemeral_environments"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Set when the env was seeded from a completed job. Nullable so an env
    # can predate the job it'll eventually carry.
    source_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    destination_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    schema_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # pending → provisioning → ready → expired → revoked → failed
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", server_default="pending"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Phase 61 F18 — controller-owned fields. Populated by the provision
    # task once Docker reports the container has started; cleared by the
    # sweep task on TTL expiry.
    container_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    host_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connection_string: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provisioning_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
