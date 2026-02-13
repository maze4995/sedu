from pydantic import BaseModel, Field


class QuestionDetailResponse(BaseModel):
    questionId: str
    setId: str
    numberLabel: str | None = None
    orderIndex: int
    reviewStatus: str
    confidence: float | None = None
    ocrText: str | None = None
    metadata: dict = Field(default_factory=dict)
    structure: dict = Field(default_factory=dict)


class QuestionReprocessResponse(BaseModel):
    ok: bool = True
    questionId: str
    setId: str
    reviewStatus: str
