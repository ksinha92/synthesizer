"""Ephemeral provisioning — controller-owned columns + sweep index.

Revision ID: 029
Revises: 028
Create Date: 2026-05-17

Phase 61 F18. Migration 021 stood up the lifecycle row; this one adds
the columns the data-copy controller actually writes into:

* ``container_id`` — docker container id, stamped after ``docker run``.
* ``host_port`` — random port the container's DB is bound to.
* ``connection_string`` — DSN the UI surfaces in GET responses; null
  until the env reaches ``ready``.
* ``ready_at`` / ``revoked_at`` / ``provisioning_started_at`` —
  lifecycle timestamps the sweep task uses to detect stuck rows and the
  UI uses to render age.

The ``ix_ephemeral_status_expires`` index already exists from migration
021 under the name ``ix_ephemeral_environments_status_expires_at``, so
we add the shorter name as well for the sweep task's query plan. Using
``IF NOT EXISTS`` keeps both fresh installs and upgrades correct.
"""

from alembic import op
import sqlalchemy as sa


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ephemeral_environments",
        sa.Column("container_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "ephemeral_environments",
        sa.Column("host_port", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ephemeral_environments",
        sa.Column("connection_string", sa.String(512), nullable=True),
    )
    op.add_column(
        "ephemeral_environments",
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ephemeral_environments",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ephemeral_environments",
        sa.Column(
            "provisioning_started_at", sa.DateTime(timezone=True), nullable=True
        ),
    )

    # Sweep-task index. ``IF NOT EXISTS`` because migration 021 already
    # created an index over the same column pair under a longer name --
    # both fresh DBs and upgrades land in the same state.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ephemeral_status_expires "
        "ON ephemeral_environments (status, expires_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ephemeral_status_expires")
    op.drop_column("ephemeral_environments", "provisioning_started_at")
    op.drop_column("ephemeral_environments", "revoked_at")
    op.drop_column("ephemeral_environments", "ready_at")
    op.drop_column("ephemeral_environments", "connection_string")
    op.drop_column("ephemeral_environments", "host_port")
    op.drop_column("ephemeral_environments", "container_id")
