"""Asset schemas."""

from pydantic import BaseModel, Field


class AssetDetailResponse(BaseModel):
    assetId: str
    questionId: str
    type: str
    bbox: dict = Field(default_factory=dict)

