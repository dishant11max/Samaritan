"""
Alembic environment configuration for Samaritan.

Uses the synchronous engine to keep Alembic simple — async Alembic
requires a separate runner and adds complexity with minimal benefit.
The ``DATABASE_URL`` is pulled from ``app.core.config.settings`` so that
no credentials are ever duplicated in ``alembic.ini``.
"""

from __future__ import annotations

import sys
import os
from logging.config import fileConfig
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the backend/ directory is on sys.path so ``app.*`` imports resolve
# when Alembic is invoked from the project root.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import settings — loads .env automatically.
from app.core.config import settings

# Import Base and ALL models so autogenerate detects every table.
from app.db.base import Base
import app.db.models  # noqa: F401 — registers all models on Base.metadata

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url from application settings (never read from alembic.ini).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Emits SQL to stdout without needing a live database connection.
    Useful for generating migration scripts for review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using a live database connection.

    Uses ``NullPool`` to avoid connection pooling during migrations —
    each migration run opens and closes its own connection cleanly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
