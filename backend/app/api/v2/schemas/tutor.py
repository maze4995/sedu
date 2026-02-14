from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

HintLevel = Literal["weak", "medium", "strong"]
ChatRole = Literal["user", "ai"]


class ChatTurn(BaseModel):
    role: ChatRole
    text: str


class HintRequest(BaseModel):
    level: HintLevel = "weak"
    recentChat: list[ChatTurn] = Field(default_factory=list)
    strokeSummary: str | None = None


class HintResponse(BaseModel):
    questionId: str
    level: HintLevel
    hint: str
    model: str = "mock-tutor-v2"
