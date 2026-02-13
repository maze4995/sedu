"""Repository helpers for extraction jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extraction_job import ExtractionJob
from app.models.set import Set
from app.utils.ids import new_public_id


class ActiveExtractionJobExistsError(RuntimeError):
    """Raised when the target set already has an active extraction job."""

    def __init__(self, active_job_public_id: str):
        super().__init__(f"Active extraction job already exists: {active_job_public_id}")
        self.active_job_public_id = active_job_public_id


def get_active_job_for_set(db: Session, *, set_obj: Set) -> ExtractionJob | None:
    stmt = (
        select(ExtractionJob)
        .where(
            ExtractionJob.set_id == set_obj.id,
            ExtractionJob.status.in_(("queued", "running")),
        )
        .order_by(ExtractionJob.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def create_job(
    db: Session,
    *,
    set_obj: Set,
    options: dict[str, Any] | None = None,
) -> ExtractionJob:
    active = get_active_job_for_set(db, set_obj=set_obj)
    if active is not None:
        raise ActiveExtractionJobExistsError(active.public_id)

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
