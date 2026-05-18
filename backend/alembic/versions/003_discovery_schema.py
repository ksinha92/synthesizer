"""Discovery schema + jobs table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovered_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connections.id"), nullable=False, index=True),
        sa.Column("schema_name", sa.String(255), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "discovered_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("schema_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovered_schemas.id"), nullable=False, index=True),
        sa.Column("table_name", sa.String(255), nullable=False),
        sa.Column("row_count", sa.Integer(), default=0),
        sa.Column("size_bytes", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "discovered_columns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovered_tables.id"), nullable=False, index=True),
        sa.Column("column_name", sa.String(255), nullable=False),
        sa.Column("data_type", sa.String(100), nullable=False),
        sa.Column("is_nullable", sa.Boolean(), default=True),
        sa.Column("is_primary_key", sa.Boolean(), default=False),
        sa.Column("is_foreign_key", sa.Boolean(), default=False),
        sa.Column("fk_references", postgresql.JSONB(), nullable=True),
        sa.Column("sample_values", postgresql.JSONB(), nullable=True),
        sa.Column("stats", postgresql.JSONB(), nullable=True),
        sa.Column("pii_type", sa.String(50), default="none", index=True),
        sa.Column("pii_confidence", postgresql.JSONB(), nullable=True),
        sa.Column("classification", sa.String(50), default="needs_review"),
        sa.Column("override_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("override_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "discovered_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("schema_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovered_schemas.id"), nullable=False, index=True),
        sa.Column("source_table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_column_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_column_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), default=1.0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_project_status", "jobs", ["project_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_project_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("discovered_relationships")
    op.drop_table("discovered_columns")
    op.drop_table("discovered_tables")
    op.drop_table("discovered_schemas")
