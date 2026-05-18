"""Add local password auth columns to users.

Revision ID: 030
Revises: 029
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "force_password_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Case-insensitive lookup index. PostgreSQL supports functional unique indexes.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_lower "
        "ON users (LOWER(email))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_users_email_lower")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "force_password_change")
    op.drop_column("users", "password_hash")
