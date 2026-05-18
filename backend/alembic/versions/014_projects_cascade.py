"""Add ON DELETE CASCADE to all FKs referencing projects.id.

Revision ID: 014
Revises: 013
Create Date: 2026-05-16
"""

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


# (table, constraint) for every FK currently pointing at projects.id.
# Constraint names are the postgres defaults: "<table>_project_id_fkey".
PROJECT_FK_TABLES = [
    "compliance_reports",
    "connections",
    "jobs",
    "masking_policies",
    "project_members",
    "subset_configs",
    "synthetic_configs",
    "webhooks",
    "workflows",
]


def upgrade() -> None:
    for table in PROJECT_FK_TABLES:
        constraint = f"{table}_project_id_fkey"
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table="projects",
            local_cols=["project_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    for table in PROJECT_FK_TABLES:
        constraint = f"{table}_project_id_fkey"
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table="projects",
            local_cols=["project_id"],
            remote_cols=["id"],
        )
