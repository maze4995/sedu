"""Tests for set listing filters."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.set import Set
from app.repo.sets import list_sets


def test_list_sets_filters_by_status():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        db.add_all([
            Set(public_id="set_ready", status="ready", question_count=3),
            Set(public_id="set_review", status="needs_review", question_count=2),
        ])
        db.commit()

        rows = list_sets(db, status="ready", limit=10, offset=0)
        assert len(rows) == 1
        assert rows[0].public_id == "set_ready"
    finally:
        db.close()
