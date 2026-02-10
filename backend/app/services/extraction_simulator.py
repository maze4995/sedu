"""Fake extraction pipeline for MVP UI testing.

Simulates progress stages and generates placeholder questions.
Runs as a background task after an extraction job is created.

When real question crop images are available, the OCR step will call
Vision OCR via ``app.pipeline.ocr_step.run_ocr_for_question``.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import _get_session_factory
from app.models.extraction_job import ExtractionJob
from app.models.question import Question
from app.models.set import Set
from app.utils.ids import new_public_id

logger = logging.getLogger(__name__)

STAGES: list[tuple[str, float]] = [
    ("preprocess", 0.10),
    ("layout_analysis", 0.30),
    ("crop_questions", 0.50),
    ("ocr", 0.70),
    ("structuring", 0.90),
]

QUESTION_COUNT = 5


def _load_job_and_set(db: Session, job_public_id: str) -> tuple[ExtractionJob, Set] | None:
    stmt = select(ExtractionJob).where(ExtractionJob.public_id == job_public_id)
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        return None
    set_obj = db.get(Set, job.set_id)
    if set_obj is None:
        return None
    return job, set_obj


def _run_ocr_if_available(db: Session, question: Question) -> None:
    """Run Vision OCR on a question crop if image bytes are available.

    TODO: Once real cropping is implemented, replace this with actual
    image bytes from the crop step:

        from app.pipeline.ocr_step import run_ocr_for_question
        image_bytes = load_crop_image(question)
        run_ocr_for_question(db, question, image_bytes)
    """
    # No crop images in simulator mode — skip real OCR.
    pass


def run_fake_extraction(job_public_id: str) -> None:
    """Simulate extraction stages and generate placeholder questions.

    Designed to run in a background thread / FastAPI BackgroundTasks.
    Opens its own DB session so the request session can be closed safely.
    """
    db: Session = _get_session_factory()()
    try:
        result = _load_job_and_set(db, job_public_id)
        if result is None:
            logger.error("Job %s not found, aborting simulator", job_public_id)
            return

        job, set_obj = result

        # Mark running
        job.status = "running"
        db.commit()

        # Progress through stages
        for stage_name, progress in STAGES:
            time.sleep(0.7)
            job.stage = stage_name
            job.progress = progress
            db.commit()

        # Generate placeholder questions
        time.sleep(0.5)
        for i in range(1, QUESTION_COUNT + 1):
            q = Question(
                public_id=new_public_id("q_"),
                set_id=set_obj.id,
                order_index=i,
                number_label=str(i),
                ocr_text=f"예시 문제 텍스트 {i}",
                structure={
                    "stem": f"예시 문제 {i}",
                    "choices": ["A", "B", "C", "D"],
                },
                metadata_json={
                    "difficulty": "중",
                    "unitPath": ["통합과학", "예시 단원"],
                },
                confidence=0.85,
                review_status="auto_ok",
            )
            db.add(q)
            db.flush()

            # Hook: run real OCR when crop images become available.
            _run_ocr_if_available(db, q)

        # Finalise
        set_obj.status = "ready"
        set_obj.question_count = QUESTION_COUNT
        job.status = "done"
        job.stage = "done"
        job.progress = 1.0
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("Fake extraction complete for job %s", job_public_id)
    except Exception:
        logger.exception("Fake extraction failed for job %s", job_public_id)
        try:
            db.rollback()
            result = _load_job_and_set(db, job_public_id)
            if result is not None:
                job, set_obj = result
                job.status = "failed"
                job.error_message = "Simulator error"
                set_obj.status = "error"
                db.commit()
        except Exception:
            logger.exception("Failed to mark job as failed")
    finally:
        db.close()
