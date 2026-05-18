"""Output mode on synthetic/subset configs + is_virtual on discovered_relationships.

Revision ID: 020
Revises: 019
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Destinations: how should generated output land?
    # Allowed values handled at API layer:
    #   same_database | different_connection | download_zip | s3
    op.add_column(
        "synthetic_configs",
        sa.Column(
            "output_mode",
            sa.String(50),
            nullable=False,
            server_default="same_database",
        ),
    )
    op.add_column(
        "subset_configs",
        sa.Column(
            "output_mode",
            sa.String(50),
            nullable=False,
            server_default="same_database",
        ),
    )

    # Virtual FK flag on discovered_relationships
    op.add_column(
        "discovered_relationships",
        sa.Column(
            "is_virtual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("discovered_relationships", "is_virtual")
    op.drop_column("subset_configs", "output_mode")
    op.drop_column("synthetic_configs", "output_mode")
