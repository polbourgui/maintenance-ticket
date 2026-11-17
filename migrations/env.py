from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401  (registers tables)
from app.db.base import Base
from app.db.session import create_db_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
# Only the DB URL is needed here: do not require the full Settings (e.g. secret key) to migrate.
DATABASE_URL = os.environ.get("APP_DATABASE_URL", "sqlite:///./maintenance.db")


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(DATABASE_URL)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite-compatible ALTERs
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
