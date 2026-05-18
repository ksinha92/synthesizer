"""Webhook security hardening — raw-secret HMAC + persistent delivery queue.

Revision ID: 027
Revises: 026
Create Date: 2026-05-17

Phase 60 F14. Adds two columns to ``webhooks``:

* ``secret_encrypted`` (``LargeBinary``, nullable) — Fernet-encrypted raw
  signing secret. Receivers possessing the raw secret can now reproduce
  the HMAC of ``f"{ts}.{body}"`` and verify the request.
* ``legacy_signing`` (``Boolean``, default ``true``) — gate for the 90-day
  deprecation path. Pre-v0.9 webhooks keep signing with ``secret_hash`` as
  the HMAC key (which is the bug we're fixing) and emit a
  ``X-Webhook-Legacy-Signing: true`` header so receivers know to switch.

Also creates ``webhook_deliveries`` for replay UI / persistent retry:
worker process exits no longer drop in-flight dispatches.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "webhooks",
        sa.Column("secret_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "webhooks",
        sa.Column(
            "legacy_signing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "webhook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Index used by the periodic redrive task that picks up rows still
    # pending or whose ``next_retry_at`` has elapsed.
    op.create_index(
        "ix_webhook_deliveries_status_next_retry",
        "webhook_deliveries",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_deliveries_status_next_retry",
        table_name="webhook_deliveries",
    )
    op.drop_table("webhook_deliveries")
    op.drop_column("webhooks", "legacy_signing")
    op.drop_column("webhooks", "secret_encrypted")
