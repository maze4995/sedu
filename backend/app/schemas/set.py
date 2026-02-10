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

