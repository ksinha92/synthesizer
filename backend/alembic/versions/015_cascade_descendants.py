"""Cascade descendant FKs so project deletion cleans up its full subtree.

Migration 014 set ON DELETE CASCADE on every direct FK to projects.id, but
descendant tables (discovered_*, masking_rules, *_configs.source_connection_id)
still defaulted to NO ACTION. Cascading a project delete would propagate to
connections and masking_policies, then fail at the descendant FK boundary.
This also adds the missing file_schemas → projects FK (migration 013 left it
as a bare project_id column with no constraint, allowing orphan rows).

Revision ID: 015
Revises: 014
Create Date: 2026-05-16
"""

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


# (table, constraint, referent, local_col, remote_col)
DESCENDANT_FKS = [
    ("discovered_columns", "discovered_columns_table_id_fkey", "discovered_tables", "table_id", "id"),
    ("discovered_relationships", "discovered_relationships_schema_id_fkey", "discovered_schemas", "schema_id", "id"),
    ("discovered_schemas", "discovered_schemas_connection_id_fkey", "connections", "connection_id", "id"),
    ("discovered_tables", "discovered_tables_schema_id_fkey", "discovered_schemas", "schema_id", "id"),
    ("masking_rules", "masking_rules_policy_id_fkey", "masking_policies", "policy_id", "id"),
    ("subset_configs", "subset_configs_source_connection_id_fkey", "connections", "source_connection_id", "id"),
    ("synthetic_configs", "synthetic_configs_source_connection_id_fkey", "connections", "source_connection_id", "id"),
]

FILE_SCHEMAS_FK = "file_schemas_project_id_fkey"


def upgrade() -> None:
    for table, constraint, referent, local, remote in DESCENDANT_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table=referent,
            local_cols=[local],
            remote_cols=[remote],
            ondelete="CASCADE",
        )

    # file_schemas was created in 013 without a FK constraint on project_id.
    # Clean up any orphans first so the new constraint can be added safely.
    op.execute(
        "DELETE FROM file_schemas WHERE project_id NOT IN (SELECT id FROM projects)"
    )
    op.create_foreign_key(
        FILE_SCHEMAS_FK,
        source_table="file_schemas",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(FILE_SCHEMAS_FK, "file_schemas", type_="foreignkey")

    for table, constraint, referent, local, remote in DESCENDANT_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table=referent,
            local_cols=[local],
            remote_cols=[remote],
        )
