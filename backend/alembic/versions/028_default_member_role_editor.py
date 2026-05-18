"""Default existing project members to editor; new rows default to viewer.

Revision ID: 028
Revises: 027
Create Date: 2026-05-17

Phase 60 F15. The ``project_members`` table from migration 010 already
defaulted ``role`` to ``viewer`` server-side, but rows written before
this migration may have NULL or empty strings (no app-side validation
was enforced for that column). Bring them up to ``editor`` so existing
collaborators are not locked out of writes when the RBAC dependency
turns on across every feature router.

Going forward, new rows still default to ``viewer`` — admin promotes
explicitly. The migration just ensures backfill + NOT NULL.
"""

from alembic import op
import sqlalchemy as sa


revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill any historical rows that lost their default.
    op.execute(
        "UPDATE project_members SET role = 'editor' "
        "WHERE role IS NULL OR role = ''"
    )
    # NULL is no longer acceptable; new rows still default to 'viewer'.
    op.alter_column(
        "project_members",
        "role",
        existing_type=sa.String(50),
        nullable=False,
        server_default=sa.text("'viewer'"),
    )


def downgrade() -> None:
    op.alter_column(
        "project_members",
        "role",
        existing_type=sa.String(50),
        nullable=True,
        server_default=None,
    )
