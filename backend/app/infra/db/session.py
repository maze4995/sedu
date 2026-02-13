from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.infra.db.base import Base


def _normalize_database_url(raw_url: str | None) -> str:
    if raw_url:
        if raw_url.startswith("postgres://"):
            return raw_url.replace("postgres://", "postgresql+psycopg://", 1)
        if raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
            return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if raw_url.startswith("sqlite:///"):
            path_part = raw_url.removeprefix("sqlite:///")
            if path_part and path_part != ":memory:" and not path_part.startswith("/"):
                return f"sqlite:///{Path(path_part).resolve()}"
        return raw_url

    default_path = Path(__file__).resolve().parents[3] / "sedu_v2.db"
    return f"sqlite:///{default_path}"


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    database_url = _normalize_database_url(settings.database_url)

    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_engine(database_url, **kwargs)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    # Ensure ORM models are imported so metadata is populated.
    from app.infra.db import models as _models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
