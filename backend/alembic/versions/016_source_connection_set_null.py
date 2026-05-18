"""Switch cross-project source_connection_id FKs from CASCADE to SET NULL.

Migration 015 made every descendant FK ON DELETE CASCADE so a project delete
cleans up its full subtree. But subset_configs.source_connection_id and
synthetic_configs.source_connection_id can legitimately point at a connection
in *another* project, so a CASCADE on those FKs would silently delete configs
in unrelated projects when a connection's owning project is deleted.

Switch those two FKs to ON DELETE SET NULL. Configs in other projects survive
with source_connection_id = NULL — the UI should flag them as needing a new
source. The columns are widened to nullable for the SET NULL behavior.

Revision ID: 016
Revises: 015
Create Date: 2026-05-16
"""

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


CROSS_PROJECT_FKS = [
    ("subset_configs", "subset_configs_source_connection_id_fkey"),
    ("synthetic_configs", "synthetic_configs_source_connection_id_fkey"),
]


def upgrade() -> None:
    for table, constraint in CROSS_PROJECT_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.alter_column(table, "source_connection_id", nullable=True)
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table="connections",
            local_cols=["source_connection_id"],
            remote_cols=["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table, constraint in CROSS_PROJECT_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        # Existing NULLs would block re-tightening to NOT NULL — leave nullable
        # in the downgrade, but restore the prior CASCADE behavior.
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table="connections",
            local_cols=["source_connection_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )
