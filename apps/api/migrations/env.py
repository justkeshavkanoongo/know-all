from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.database import Base
from app import quest_tables  # noqa: F401 - register metadata

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value or not value.startswith("postgresql+psycopg://"):
        raise RuntimeError("Set DATABASE_URL to a postgresql+psycopg:// URL before running migrations")
    return value


def run_migrations_offline() -> None:
    context.configure(url=url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
