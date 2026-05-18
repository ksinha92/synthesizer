"""DLQ unique index on original_job_id.

Revision ID: 024
Revises: 022
Create Date: 2026-05-17

Phase 59 F8. The ``task_failure`` signal in ``celery_app.py`` writes a
``DeadLetterJobModel`` row when a Celery task exhausts its retries. To make
that insert idempotent (Celery may fire the same terminal failure under
edge cases, and admin retries should never duplicate the dead-letter row),
we use ``ON CONFLICT (original_job_id) DO NOTHING`` — which requires a
unique constraint or unique index on that column.

The existing model only declares a non-unique index. This migration adds
the unique index needed by the upsert. There is no Phase 57 migration 023
in the tree, so we hang directly off 022.
"""

from alembic import op


revision = "024"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_dead_letter_jobs_original_job_id_unique",
        "dead_letter_jobs",
        ["original_job_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dead_letter_jobs_original_job_id_unique",
        table_name="dead_letter_jobs",
    )
