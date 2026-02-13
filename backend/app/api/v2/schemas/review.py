from typing import Literal

from pydantic import BaseModel, Field

ReviewStatus = Literal["unreviewed", "auto_ok", "auto_flagged", "approved", "rejected"]


class ReviewQueueItem(BaseModel):
    questionId: str
    setId: str
    numberLabel: str | None = None
    orderIndex: int
    reviewStatus: ReviewStatus
    confidence: float | None = None
    metadata: dict = Field(default_factory=dict)


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    count: int


class ReviewPatchRequest(BaseModel):
    reviewer: str
    reviewStatus: ReviewStatus
    note: str | None = None
    metadataPatch: dict = Field(default_factory=dict)


class ReviewPatchResponse(BaseModel):
    questionId: str
    reviewStatus: ReviewStatus
    metadata: dict = Field(default_factory=dict)
