"""Legacy compliance reports flag.

Revision ID: 022
Revises: 021
Create Date: 2026-05-17

Phase 57 F1. Compliance reports generated before this migration ran were
produced by a handler that hard-coded empty PII/masking lists, so every
HIPAA/GDPR/CCPA PDF shipped with zero findings. The bug is now fixed; this
migration adds a ``legacy`` flag and back-fills it to ``true`` on every
pre-existing row so the API can warn users that those artifacts are stale.

The column is additive (nullable=False with a server_default of ``false``)
so existing rows are safe through the upgrade. Downgrade simply drops the
column.
"""

from alembic import op
import sqlalchemy as sa


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "compliance_reports",
        sa.Column(
            "legacy",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Back-fill every row that already existed — those were all generated
    # by the broken pre-v0.9 handler.
    op.execute("UPDATE compliance_reports SET legacy = true")


def downgrade() -> None:
    op.drop_column("compliance_reports", "legacy")
