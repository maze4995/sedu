"""Repository helpers for question variants."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_variant import QuestionVariant


def create_question_variant(
    db: Session,
    *,
    question: Question,
    variant_type: str,
    body: str,
    answer: str | None,
    explanation: str | None,
    model: str | None,
) -> QuestionVariant:
    row = QuestionVariant(
        question_id=question.id,
        variant_type=variant_type,
        body=body,
        answer=answer,
        explanation=explanation,
        model=model,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_question_variants(db: Session, *, question: Question) -> list[QuestionVariant]:
    stmt = (
        select(QuestionVariant)
        .where(QuestionVariant.question_id == question.id)
        .order_by(QuestionVariant.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
