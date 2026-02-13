"""Set schemas."""

from pydantic import BaseModel


class SetCreatedResponse(BaseModel):
    setId: str
    status: str


class SetDetailResponse(BaseModel):
    setId: str
    status: str
    title: str | None = None
    sourceFilename: str | None = None
    sourceMime: str | None = None
    sourceSize: int | None = None
    questionCount: int = 0


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
