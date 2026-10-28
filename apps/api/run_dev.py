"""Preflight the configured local PostgreSQL database, then start Uvicorn."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.database import DatabaseConfigurationError, get_engine  # noqa: E402


def preflight() -> None:
    secret = os.environ.get("QUEST_SESSION_SECRET", "")
    if len(secret) < 32 or secret == "replace-with-at-least-32-random-bytes":
        raise RuntimeError("QUEST_SESSION_SECRET must be set to at least 32 characters before starting the API.")
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = set(connection.scalars(text("SELECT version_num FROM alembic_version")))
        expected = ScriptDirectory.from_config(Config("apps/api/alembic.ini")).get_heads()
    except DatabaseConfigurationError as exc:
        raise RuntimeError("DATABASE_URL must be set to a postgresql+psycopg:// URL before starting the API.") from exc
    except SQLAlchemyError as exc:
        raise RuntimeError("PostgreSQL is unavailable or migrations are missing; check DATABASE_URL and run `pnpm db:upgrade`.") from exc
    if current != set(expected):
        raise RuntimeError("The configured database is not at the latest migration; run `pnpm db:upgrade`.")


if __name__ == "__main__":
    try:
        preflight()
    except RuntimeError as exc:
        print(f"API startup blocked: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    import uvicorn

    uvicorn.run(
        "app.main:app",
        app_dir="apps/api",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload=True,
    )
