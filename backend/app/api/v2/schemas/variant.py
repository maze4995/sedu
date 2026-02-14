from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

VariantType = Literal["paraphrase", "numeric_swap", "concept_shift", "format_transform"]


class VariantItem(BaseModel):
    variantId: str
    questionId: str
    variantType: VariantType
    body: str
    answer: str | None = None
    explanation: str | None = None
    model: str | None = None
    createdAt: str


class VariantListResponse(BaseModel):
    questionId: str
    variants: list[VariantItem]


class VariantCreateRequest(BaseModel):
    variantType: VariantType = "paraphrase"


class VariantCreateResponse(BaseModel):
    questionId: str
    variant: VariantItem
