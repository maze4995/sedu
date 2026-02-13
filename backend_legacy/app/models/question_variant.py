"""ORM model for generated question variants."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.question import Question


class QuestionVariant(Base):
    __tablename__ = "question_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )

    variant_type: Mapped[str] = mapped_column(Text, nullable=False, default="paraphrase")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    question: Mapped["Question"] = relationship(back_populates="variants")
