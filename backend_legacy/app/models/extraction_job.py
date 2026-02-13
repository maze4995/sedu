"""ORM model for extraction jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.set import Set


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

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

    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    stage: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    options: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

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
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    set: Mapped["Set"] = relationship(back_populates="extraction_jobs")
