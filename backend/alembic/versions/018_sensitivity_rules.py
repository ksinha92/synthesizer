"""Sensitivity rules table.

Revision ID: 018
Revises: 017
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sensitivity_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("match_type", sa.String(50), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("suggested_pii_type", sa.String(50), nullable=False),
        sa.Column(
            "suggested_preset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generator_presets.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sensitivity_rules_priority", "sensitivity_rules", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_sensitivity_rules_priority", table_name="sensitivity_rules")
    op.drop_table("sensitivity_rules")
