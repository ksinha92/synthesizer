"""Ephemeral environments — tracked, time-limited destinations for generated data.

Revision ID: 021
Revises: 020
Create Date: 2026-05-17

T3.1 (Tonic-parity). An ephemeral environment is a record linking a
project + destination connection + an expiry. The data-copy controller
that actually populates the destination is a follow-up task; this table
gives the surface + lifecycle so the rest of the system can plan around
it.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ephemeral_environments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        # Job whose output seeded this environment. Nullable because users
        # can stand up an empty ephemeral and seed it later.
        sa.Column(
            "source_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Where the data physically lives. Nullable so revoked envs keep
        # an audit-trail row even after the destination is removed.
        sa.Column(
            "destination_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Schema/database name the controller scoped the data into.
        sa.Column("schema_name", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        # pending → provisioning → ready → expired → revoked
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_ephemeral_environments_status_expires_at",
        "ephemeral_environments",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ephemeral_environments_status_expires_at",
        table_name="ephemeral_environments",
    )
    op.drop_table("ephemeral_environments")
