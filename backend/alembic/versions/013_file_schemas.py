"""File schemas table for v0.7 file-based synthetic generation.

Revision ID: 013
Revises: 012
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("file_format", sa.String(50), nullable=False),
        sa.Column("encoding", sa.String(50), nullable=False, server_default="ascii"),
        sa.Column("record_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_rdw", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("output_filename", sa.String(255), nullable=True),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("file_schemas")
