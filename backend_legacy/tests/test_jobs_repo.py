"""Tests for extraction job dedup guard."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.set import Set
from app.repo.jobs import ActiveExtractionJobExistsError, create_job


def test_create_job_blocks_duplicate_active_job():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        set_obj = Set(public_id="set_01", status="created", question_count=0)
        db.add(set_obj)
        db.commit()
        db.refresh(set_obj)

        first = create_job(db, set_obj=set_obj)
        assert first.status == "queued"

        try:
            create_job(db, set_obj=set_obj)
            assert False, "Expected ActiveExtractionJobExistsError"
        except ActiveExtractionJobExistsError as exc:
            assert exc.active_job_public_id == first.public_id
    finally:
        db.close()


def test_create_job_allows_new_job_after_completion():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        set_obj = Set(public_id="set_02", status="created", question_count=0)
        db.add(set_obj)
        db.commit()
        db.refresh(set_obj)

        first = create_job(db, set_obj=set_obj)
        first.status = "done"
        db.add(first)
        db.commit()

        second = create_job(db, set_obj=set_obj)
        assert second.public_id != first.public_id
        assert second.status == "queued"
    finally:
        db.close()
