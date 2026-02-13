from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

SetStatus = Literal["created", "extracting", "ready", "needs_review", "error"]
JobStatus = Literal["queued", "running", "done", "failed"]
ReviewStatus = Literal["unreviewed", "auto_ok", "auto_flagged", "approved", "rejected"]


@dataclass
class JobRecord:
    job_id: str
    set_id: str
    status: JobStatus
    stage: str | None = None
    percent: float = 0.0
    error_message: str | None = None


@dataclass
class JobEventRecord:
    job_id: str
    status: JobStatus
    stage: str | None = None
    percent: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SetRecord:
    set_id: str
    status: SetStatus
    title: str | None = None
    source_filename: str | None = None
    source_mime: str | None = None
    source_size: int | None = None
    question_count: int = 0


@dataclass
class QuestionRecord:
    question_id: str
    set_id: str
    number_label: str | None
    order_index: int
    review_status: ReviewStatus
    confidence: float | None
    metadata: dict[str, Any] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)
    ocr_text: str | None = None


@dataclass
class ReviewActionRecord:
    question_id: str
    reviewer: str
    review_status: ReviewStatus
    note: str | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
