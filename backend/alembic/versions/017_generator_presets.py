"""Generator presets table + masking_rules.preset_id FK.

Revision ID: 017
Revises: 016
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generator_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("generator_type", sa.String(50), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("consistency", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column(
        "masking_rules",
        sa.Column("preset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "masking_rules_preset_id_fkey",
        source_table="masking_rules",
        referent_table="generator_presets",
        local_cols=["preset_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_masking_rules_preset_id", "masking_rules", ["preset_id"])


def downgrade() -> None:
    op.drop_index("ix_masking_rules_preset_id", table_name="masking_rules")
    op.drop_constraint("masking_rules_preset_id_fkey", "masking_rules", type_="foreignkey")
    op.drop_column("masking_rules", "preset_id")
    op.drop_table("generator_presets")
