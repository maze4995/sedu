from pydantic import BaseModel


class SetSummaryResponse(BaseModel):
    setId: str
    status: str
    title: str | None = None
    questionCount: int = 0
    sourceFilename: str | None = None


class SetListResponse(BaseModel):
    sets: list[SetSummaryResponse]
    limit: int
    offset: int


class SetDetailResponse(BaseModel):
    setId: str
    status: str
    latestJobId: str | None = None
    title: str | None = None
    sourceFilename: str | None = None
    sourceMime: str | None = None
    sourceSize: int | None = None
    questionCount: int = 0


class SetQuestionSummary(BaseModel):
    questionId: str
    numberLabel: str | None = None
    orderIndex: int
    reviewStatus: str
    confidence: float | None = None
    croppedImageUrl: str | None = None


class SetQuestionListResponse(BaseModel):
    setId: str
    questions: list[SetQuestionSummary]


class SetDeleteResponse(BaseModel):
    ok: bool = True
    setId: str
