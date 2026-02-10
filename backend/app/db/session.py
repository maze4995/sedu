"""Database session configuration."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_SQLITE_DEFAULT = "sqlite:///" + str(
    Path(__file__).resolve().parent.parent.parent / "sedu_dev.db"
)


def _get_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL")

    if not raw_url:
        logger.warning("DATABASE_URL not set — using SQLite at %s", _SQLITE_DEFAULT)
        return _SQLITE_DEFAULT

    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)

    if raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return raw_url


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    url = _get_database_url()
    kwargs: dict = {}

    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True

    engine = create_engine(url, **kwargs)

    # Enable WAL mode for SQLite (better concurrent access).
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def _get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_get_engine(),
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    db = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()
