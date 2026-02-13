"""ORM model for questions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.question_variant import QuestionVariant
    from app.models.set import Set


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    public_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)

    set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sets.id", ondelete="CASCADE"),
        nullable=False,
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    number_label: Mapped[str | None] = mapped_column(Text)

    original_image_key: Mapped[str | None] = mapped_column(Text)
    cropped_image_key: Mapped[str | None] = mapped_column(Text)
    ocr_text: Mapped[str | None] = mapped_column(Text)

    structure: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    confidence: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    set: Mapped["Set"] = relationship(back_populates="questions")
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
    variants: Mapped[list["QuestionVariant"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
