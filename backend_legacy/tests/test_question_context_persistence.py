"""Tests for persisted structuring context from pipeline question creation."""

from __future__ import annotations

import json
import uuid

from app.models.question import Question
from app.pipeline.orchestrator import _apply_page_ocr_to_question, _build_question_context_metadata
from app.pipeline.structure_step import build_structure_input


def test_pipeline_question_context_persisted_and_used_for_structuring():
    bbox = {"x1": 0, "y1": 10, "x2": 100, "y2": 200, "number_label": "1"}
    metadata = _build_question_context_metadata(source_page=3, bbox=bbox)

    question = Question(
        public_id="q_01JTESTCTX0001",
        set_id=uuid.uuid4(),
        order_index=1,
        number_label="1",
        metadata_json=metadata,
        structure={},
        review_status="unreviewed",
    )

    # Mimic pipeline OCR merge after question creation.
    page_tokens = [
        {"text": "1.", "bbox": {"x1": 5, "y1": 20, "x2": 15, "y2": 30}, "conf": 0.95},
        {"text": "문제", "bbox": {"x1": 20, "y1": 20, "x2": 60, "y2": 30}, "conf": 0.93},
    ]
    _apply_page_ocr_to_question(question, page_tokens, bbox)

    assert question.metadata_json["source_page"] == 3
    assert question.metadata_json["question_bbox"] == {"x1": 0, "y1": 10, "x2": 100, "y2": 200}

    structuring_input = build_structure_input(question)
    assert structuring_input["pageNo"] == "3"
    assert json.loads(structuring_input["questionBBox"]) == {
        "x1": 0,
        "y1": 10,
        "x2": 100,
        "y2": 200,
    }
