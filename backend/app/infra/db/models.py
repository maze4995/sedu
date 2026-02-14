from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import Base


class SetRow(Base):
    __tablename__ = "sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    title: Mapped[str | None] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(Text)
    source_mime: Mapped[str | None] = mapped_column(Text)
    source_size: Mapped[int | None] = mapped_column(Integer)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list[JobRow]] = relationship(back_populates="set", cascade="all, delete-orphan")
    questions: Mapped[list[QuestionRow]] = relationship(back_populates="set", cascade="all, delete-orphan")


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("sets.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    stage: Mapped[str | None] = mapped_column(String(64))
    percent: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    set: Mapped[SetRow] = relationship(back_populates="jobs")
    events: Mapped[list[JobEventRow]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobEventRow(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str | None] = mapped_column(String(64))
    percent: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    job: Mapped[JobRow] = relationship(back_populates="events")


class QuestionRow(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("sets.id", ondelete="CASCADE"), index=True)
    number_label: Mapped[str | None] = mapped_column(String(64))
    order_index: Mapped[int] = mapped_column(Integer, default=1)
    review_status: Mapped[str] = mapped_column(String(32), default="unreviewed", index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    structure_json: Mapped[dict] = mapped_column("structure", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    set: Mapped[SetRow] = relationship(back_populates="questions")
    review_actions: Mapped[list[ReviewActionRow]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )
    variants: Mapped[list[VariantRow]] = relationship(back_populates="question", cascade="all, delete-orphan")


class ReviewActionRow(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    reviewer: Mapped[str] = mapped_column(String(128), index=True)
    review_status: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped[QuestionRow] = relationship(back_populates="review_actions")


class VariantRow(Base):
    __tablename__ = "question_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    variant_type: Mapped[str] = mapped_column(String(64), index=True)
    body: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    question: Mapped[QuestionRow] = relationship(back_populates="variants")
