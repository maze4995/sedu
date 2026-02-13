"""Repository helpers for questions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.set import Set


def list_questions_for_set(db: Session, set_obj: Set) -> list[Question]:
    stmt = (
        select(Question)
        .where(Question.set_id == set_obj.id)
        .order_by(Question.order_index.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_question_by_public_id(db: Session, public_id: str) -> Question | None:
    stmt = select(Question).where(Question.public_id == public_id)
    return db.execute(stmt).scalar_one_or_none()


def patch_question_by_public_id(
    db: Session,
    *,
    public_id: str,
    ocr_text: str | None = None,
    structure: dict | None = None,
    metadata: dict | None = None,
    review_status: str | None = None,
) -> Question | None:
    question = get_question_by_public_id(db, public_id)
    if question is None:
        return None

    if ocr_text is not None:
        question.ocr_text = ocr_text
    if structure is not None:
        question.structure = structure
    if metadata is not None:
        question.metadata_json = metadata
    if review_status is not None:
        question.review_status = review_status

    db.add(question)
    db.commit()
    db.refresh(question)
    return question

