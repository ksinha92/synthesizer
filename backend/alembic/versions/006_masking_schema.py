"""Masking policies and rules.

Revision ID: 006
Revises: 005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"

def upgrade() -> None:
    op.create_table(
        "masking_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "masking_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("masking_policies.id"), nullable=False, index=True),
        sa.Column("column_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("match_pattern", postgresql.JSONB(), nullable=True),
        sa.Column("masking_type", sa.String(50), nullable=False, server_default="redact"),
        sa.Column("masking_config", postgresql.JSONB(), nullable=True),
        sa.Column("preserve_format", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("deterministic", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table("masking_rules")
    op.drop_table("masking_policies")
