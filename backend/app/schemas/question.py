"""Question schemas."""

from pydantic import BaseModel, Field


class QuestionSummary(BaseModel):
    questionId: str
    numberLabel: str | None = None
    orderIndex: int = 0
    reviewStatus: str = "pending"


class QuestionListResponse(BaseModel):
    setId: str
    questions: list[QuestionSummary]


class QuestionDetailResponse(BaseModel):
    questionId: str
    setId: str
    numberLabel: str | None = None
    orderIndex: int = 0
    ocrText: str | None = None
    structure: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    confidence: float | None = None
    reviewStatus: str = "pending"


class QuestionPatchRequest(BaseModel):
    ocrText: str | None = None
    structure: dict | None = None
    metadata: dict | None = None
    reviewStatus: str | None = None


class OkResponse(BaseModel):
    ok: bool = True

