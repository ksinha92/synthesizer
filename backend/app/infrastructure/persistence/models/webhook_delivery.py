"""WebhookDelivery model — failed-delivery replay queue.

Phase 60 F14. Each row records a single outbound webhook attempt (or batch
of attempts against the same dispatch lifecycle). The dispatcher writes a
``pending`` row before the first POST, marks it ``sent`` once the receiver
responds 2xx, and otherwise records the final error so admins can replay
the delivery via ``POST /admin/webhook-deliveries/{id}/retry``.

The persisted queue exists because the prior dispatch path used
``asyncio.create_task`` from inside Celery worker tasks — when the
per-task event loop closed, retries silently died. Persisting deliveries
plus a periodic scan of ``status='pending'`` and ``status='failed' AND
next_retry_at <= NOW()`` makes retries survive worker restarts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class WebhookDeliveryModel(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), default=0)
    # ``pending`` -> ``sent`` on first 2xx; ``failed`` once retries are exhausted.
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"), default="pending")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
