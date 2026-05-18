"""Webhook ORM model."""

import uuid

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WebhookModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "webhooks"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    events: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["job.completed", "job.failed"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # ``secret_hash`` is the legacy column — pre-v0.9 webhooks signed bodies
    # with this value (which is a sha256 of the raw secret) as the HMAC key,
    # which receivers could never reproduce. Phase 60 F14 keeps the column
    # populated during the 90-day deprecation window so existing receivers
    # are not broken instantly.
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Fernet-encrypted raw signing secret. ``None`` for legacy rows until
    # they are rotated. New webhooks always populate this and verify via
    # the raw-secret HMAC path.
    secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Toggle controlling the deprecation path. ``True`` for pre-v0.9 rows
    # (sign with ``secret_hash`` and emit ``X-Webhook-Legacy-Signing: true``)
    # and ``False`` for v0.9+ rows (sign with the raw secret).
    legacy_signing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
