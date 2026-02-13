"""Question schemas."""

from pydantic import BaseModel, Field


class QuestionSummary(BaseModel):
    questionId: str
    numberLabel: str | None = None
    orderIndex: int = 0
    reviewStatus: str = "pending"
    croppedImageUrl: str | None = None


class QuestionListResponse(BaseModel):
    setId: str
    questions: list[QuestionSummary]


class QuestionDetailResponse(BaseModel):
    questionId: str
    setId: str
    numberLabel: str | None = None
    orderIndex: int = 0
    croppedImageUrl: str | None = None
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


class ReprocessResponse(BaseModel):
    ok: bool = True
    questionId: str
    setId: str
    reviewStatus: str


class VariantCreateRequest(BaseModel):
    variantType: str = "paraphrase"


class VariantResponse(BaseModel):
    variantId: str
    variantType: str
    body: str
    answer: str | None = None
    explanation: str | None = None
    model: str | None = None
    createdAt: str


class VariantListResponse(BaseModel):
    questionId: str
    variants: list[VariantResponse]


class HintChatMessage(BaseModel):
    role: str
    text: str


class HintRequest(BaseModel):
    level: str | None = "weak"
    recentChat: list[HintChatMessage] = Field(default_factory=list)
    strokeSummary: str | None = None


class HintResponse(BaseModel):
    questionId: str
    level: str
    hint: str
    model: str
