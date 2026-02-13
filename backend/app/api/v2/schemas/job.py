from pydantic import BaseModel


class JobDetailResponse(BaseModel):
    jobId: str
    setId: str
    status: str
    stage: str | None = None
    percent: float = 0.0
    errorMessage: str | None = None


class JobEventItem(BaseModel):
    status: str
    stage: str | None = None
    percent: float = 0.0
    createdAt: str


class JobEventListResponse(BaseModel):
    jobId: str
    events: list[JobEventItem]
