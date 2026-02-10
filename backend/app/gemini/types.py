"""Pydantic models mirroring the Gemini JSON schemas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ── QuestionStructureV1 ─────────────────────────────────────────────


class QuestionFormat(str, Enum):
    multiple_choice = "multiple_choice"
    short_answer = "short_answer"
    descriptive = "descriptive"
    true_false = "true_false"
    matching = "matching"
    unknown = "unknown"


class MaterialKind(str, Enum):
    passage = "passage"
    table_caption = "table_caption"
    figure_caption = "figure_caption"
    data = "data"
    condition = "condition"
    other = "other"


class AssetType(str, Enum):
    image = "image"
    diagram = "diagram"
    table = "table"
    graph = "graph"
    equation = "equation"
    other = "other"


class AttachTo(str, Enum):
    stem = "stem"
    materials = "materials"
    choices = "choices"


class ReviewFlag(str, Enum):
    low_ocr_confidence = "low_ocr_confidence"
    ambiguous_structure = "ambiguous_structure"
    missing_choices = "missing_choices"
    missing_stem = "missing_stem"
    overlapping_bbox = "overlapping_bbox"
    unresolved_asset = "unresolved_asset"
    other = "other"


class Material(BaseModel, extra="forbid"):
    kind: MaterialKind
    text: str


class Choice(BaseModel, extra="forbid"):
    label: str
    text: str


class AssetLink(BaseModel, extra="forbid"):
    asset_id: str
    asset_type: AssetType
    attach_to: AttachTo
    rationale: str


class Review(BaseModel, extra="forbid"):
    needs_review: bool
    flags: list[ReviewFlag]
    evidence_summary: str


class QuestionStructureV1(BaseModel, extra="forbid"):
    question_id: str
    question_format: QuestionFormat
    stem: str
    materials: list[Material]
    choices: list[Choice]
    asset_links: list[AssetLink]
    review: Review
    clean_text_preview: str


# ── SegmentationQCV1 ────────────────────────────────────────────────


class SegmentationIssue(str, Enum):
    merged_with_next = "merged_with_next"
    missing_top = "missing_top"
    missing_bottom = "missing_bottom"
    missing_left = "missing_left"
    missing_right = "missing_right"
    unclear_numbering = "unclear_numbering"
    other = "other"


class BBoxAdjustment(BaseModel, extra="forbid"):
    dx: float
    dy: float
    dw: float
    dh: float


class SegmentationQCV1(BaseModel, extra="forbid"):
    question_id: str
    is_complete: bool
    issues: list[SegmentationIssue]
    confidence: float = Field(ge=0, le=1)
    suggested_bbox_adjustment: BBoxAdjustment | None = None
    notes: str | None = None
