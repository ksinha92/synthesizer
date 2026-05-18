"""Subsetting configs.

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"

def upgrade() -> None:
    op.create_table(
        "subset_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connections.id"), nullable=False),
        sa.Column("target_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_percentage", sa.Float(), nullable=True),
        sa.Column("target_row_count", sa.Integer(), nullable=True),
        sa.Column("root_tables", postgresql.JSONB(), nullable=True),
        sa.Column("traversal_strategy", sa.String(50), server_default="upstream"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table("subset_configs")
