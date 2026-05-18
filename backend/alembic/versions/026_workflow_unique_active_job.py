"""Partial unique index — one active workflow execution per workflow.

Revision ID: 026
Revises: 025
Create Date: 2026-05-17

Phase 59 F11. Pairs with the ``SELECT FOR UPDATE`` in
``ExecuteWorkflowHandler.handle`` to guarantee a workflow has at most one
``pending`` or ``running`` job row at a time, even under racing API
calls. The application lock prevents the race on PostgreSQL; this partial
unique index is the database-level backstop so we can rely on the
constraint in tests, migrations, and other tools that touch the table
directly.

The index uses ``reference_id`` (the column ``JobModel.reference_id``
that holds the workflow UUID for ``job_type='workflow'`` rows) rather
than a non-existent ``workflow_id`` column. The partial predicate scopes
the constraint to active workflow jobs only — completed/failed/cancelled
runs do not block re-execution.
"""

from alembic import op
import sqlalchemy as sa


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_unique_active_workflow",
        "jobs",
        ["reference_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'running') AND job_type = 'workflow'"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_unique_active_workflow", table_name="jobs")
