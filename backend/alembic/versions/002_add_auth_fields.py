"""Add auth fields to users table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_sso_subject_id", "users", ["sso_subject_id"])


def downgrade() -> None:
    op.drop_index("ix_users_sso_subject_id", table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "token_version")
