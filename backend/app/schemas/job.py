"""Extraction job schemas."""

from pydantic import BaseModel


class ExtractionJobCreatedResponse(BaseModel):
    jobId: str
    setId: str
    status: str


class ExtractionJobDetailResponse(BaseModel):
    jobId: str
    setId: str
    status: str
    stage: str | None = None
    percent: float = 0.0
    errorMessage: str | None = None

