"""Drop WorkflowModel.schedule with archive.

Revision ID: 025
Revises: 024
Create Date: 2026-05-17

Phase 59 F12. The legacy ``schedule`` column on ``workflows`` was a cron
expression that was *stored but never executed* (v0.2 placeholder). The new
v0.9 design moves recurring execution to Celery beat owned outside of the
workflow row, so the column is removed from the API, ORM, and domain layer.

To preserve any human-entered cron strings (in case ops needs to migrate
them to the new scheduler later), this migration first copies non-null
schedules into ``_archived_workflow_schedules`` before dropping the
column. ``downgrade()`` recreates the column and restores values from
the archive table.
"""

from alembic import op
import sqlalchemy as sa


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Archive table — created idempotently so re-running locally is safe.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS _archived_workflow_schedules (
            workflow_id UUID PRIMARY KEY,
            schedule VARCHAR NOT NULL,
            archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Copy any non-null schedules. ON CONFLICT keeps the migration
    # idempotent in case a prior partial run already archived rows.
    op.execute(
        """
        INSERT INTO _archived_workflow_schedules (workflow_id, schedule)
        SELECT id, schedule FROM workflows WHERE schedule IS NOT NULL
        ON CONFLICT (workflow_id) DO NOTHING
        """
    )

    op.drop_column("workflows", "schedule")


def downgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("schedule", sa.String(length=100), nullable=True),
    )
    # Restore archived cron expressions back onto the workflow row.
    op.execute(
        """
        UPDATE workflows w
        SET schedule = a.schedule
        FROM _archived_workflow_schedules a
        WHERE a.workflow_id = w.id
        """
    )
