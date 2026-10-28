"""Lazy PostgreSQL connection management; no database work occurs at import time."""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


class DatabaseConfigurationError(RuntimeError):
    """Safe client-facing signal for missing/invalid database configuration."""


def database_url(*, test: bool = False) -> str:
    key = "TEST_DATABASE_URL" if test else "DATABASE_URL"
    value = os.environ.get(key)
    if not value:
        raise DatabaseConfigurationError(f"{key} is required for PostgreSQL-backed quest endpoints")
    if not value.startswith("postgresql+psycopg://"):
        raise DatabaseConfigurationError(f"{key} must use the postgresql+psycopg:// driver")
    return value


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = create_engine(database_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _factory
    get_engine()
    assert _factory is not None
    return _factory


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Test/runtime lifecycle hook; doesn't alter database contents."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
