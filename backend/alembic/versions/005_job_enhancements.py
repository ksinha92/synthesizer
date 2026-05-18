"""Job enhancements + dead letter queue.

Revision ID: 005
Revises: 004
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"

def upgrade() -> None:
    op.add_column("jobs", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("checkpoint", postgresql.JSONB(), nullable=True))
    op.add_column("jobs", sa.Column("celery_task_id", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("result_summary", postgresql.JSONB(), nullable=True))

    op.create_table(
        "dead_letter_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("original_job_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table("dead_letter_jobs")
    op.drop_column("jobs", "result_summary")
    op.drop_column("jobs", "celery_task_id")
    op.drop_column("jobs", "checkpoint")
    op.drop_column("jobs", "cancelled_at")
