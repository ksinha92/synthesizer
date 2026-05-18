"""Linked-column + consistency-group columns on masking_rules.

Revision ID: 019
Revises: 018
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "masking_rules",
        sa.Column(
            "linked_column_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
    )
    op.add_column(
        "masking_rules",
        sa.Column("consistency_group", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_masking_rules_consistency_group",
        "masking_rules",
        ["consistency_group"],
    )


def downgrade() -> None:
    op.drop_index("ix_masking_rules_consistency_group", table_name="masking_rules")
    op.drop_column("masking_rules", "consistency_group")
    op.drop_column("masking_rules", "linked_column_ids")
