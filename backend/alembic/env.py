"""Alembic environment configuration. Uses sync driver for migrations."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.infrastructure.persistence.models.base import Base

# Import all models so Base.metadata picks them up
from app.infrastructure.persistence.models import (  # noqa: F401
    connection,
    ephemeral,
    project,
    user,
    webhook,
    webhook_delivery,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use sync URL for migrations (Alembic does not support asyncpg natively)
sync_url = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/datawrangler",
)
config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
