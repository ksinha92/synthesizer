"""Synthetic configs table.

Revision ID: 004
Revises: 003
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "synthetic_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connections.id"), nullable=False),
        sa.Column("target_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tables", postgresql.JSONB(), nullable=True),
        sa.Column("generation_method", sa.String(50), nullable=False, server_default="faker"),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("nlp_prompt", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), default=100),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("synthetic_configs")
