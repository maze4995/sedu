"""Repository helpers for extraction jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extraction_job import ExtractionJob
from app.models.set import Set
from app.utils.ids import new_public_id


def create_job(
    db: Session,
    *,
    set_obj: Set,
    options: dict[str, Any] | None = None,
) -> ExtractionJob:
    set_obj.status = "extracting"

    job = ExtractionJob(
        public_id=new_public_id("job_"),
        set_id=set_obj.id,
        status="queued",
        stage="upload",
        progress=0.0,
        options=options or {},
    )

    db.add(set_obj)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job_by_public_id(db: Session, public_id: str) -> ExtractionJob | None:
    stmt = select(ExtractionJob).where(ExtractionJob.public_id == public_id)
    return db.execute(stmt).scalar_one_or_none()

