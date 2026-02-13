"""Tests for Gemini structuring pipeline step."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.pipeline.structure_step import build_structure_input, run_gemini_structuring


def _make_question(**overrides):
    defaults = {
        "public_id": "q_01JTEST0001",
        "set": SimpleNamespace(public_id="set_01JTEST0001", id="set-internal-id"),
        "structure": {
            "ocr_tokens": [
                {"text": "1.", "bbox": {"x1": 10, "y1": 20, "x2": 20, "y2": 30}, "conf": 0.98},
                {"text": "문제", "bbox": {"x1": 25, "y1": 20, "x2": 60, "y2": 30}, "conf": 0.95},
            ]
        },
        "metadata_json": {
            "source_page": 0,
            "question_bbox": {"x1": 0, "y1": 10, "x2": 100, "y2": 200},
        },
        "review_status": "unreviewed",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _valid_structured(needs_review: bool = False) -> dict:
    return {
        "question_id": "q_01JTEST0001",
        "question_format": "multiple_choice",
        "stem": "문제",
        "materials": [],
        "choices": [
            {"label": "1", "text": "A"},
            {"label": "2", "text": "B"},
        ],
        "asset_links": [],
        "review": {
            "needs_review": needs_review,
            "flags": [],
            "evidence_summary": "ok",
        },
        "clean_text_preview": "문제 A B",
    }


def test_build_structure_input_uses_ocr_tokens_json():
    question = _make_question()
    result = build_structure_input(question)

    assert result["setId"] == "set_01JTEST0001"
    assert result["questionId"] == "q_01JTEST0001"
    assert result["pageNo"] == "0"
    assert result["questionBBox"] == '{"x1": 0, "y1": 10, "x2": 100, "y2": 200}'
    assert '"text": "1."' in result["ocrTokensJson"]
    assert result["assetsJson"] == "[]"


def test_run_gemini_structuring_success_sets_parsed_and_auto_ok(monkeypatch):
    db = MagicMock()
    question = _make_question(review_status="unreviewed")
    monkeypatch.setattr("app.pipeline.structure_step._run_segmentation_qc", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        "app.pipeline.structure_step.call_gemini_structured",
        lambda **_: _valid_structured(needs_review=False),
    )

    run_gemini_structuring(db, question)

    assert "parsed_v1" in question.structure
    assert question.metadata_json["structure_model"]
    assert question.metadata_json["structured_at"]
    assert question.review_status == "auto_ok"
    assert "structure_error" not in question.metadata_json
    db.commit.assert_called()


def test_run_gemini_structuring_needs_review_sets_auto_flagged(monkeypatch):
    db = MagicMock()
    question = _make_question(review_status="unreviewed")
    monkeypatch.setattr("app.pipeline.structure_step._run_segmentation_qc", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        "app.pipeline.structure_step.call_gemini_structured",
        lambda **_: _valid_structured(needs_review=True),
    )

    run_gemini_structuring(db, question)

    assert "parsed_v1" in question.structure
    assert question.review_status == "auto_flagged"


def test_run_gemini_structuring_invalid_output_sets_error_and_flagged(monkeypatch):
    db = MagicMock()
    question = _make_question(review_status="unreviewed")
    monkeypatch.setattr("app.pipeline.structure_step._run_segmentation_qc", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        "app.pipeline.structure_step.call_gemini_structured",
        lambda **_: {"invalid": True},
    )

    run_gemini_structuring(db, question)

    assert question.review_status == "auto_flagged"
    assert "structure_error" in question.metadata_json
    assert question.metadata_json["structure_error"]["type"]
    assert question.metadata_json["structure_error"]["message"]


def test_run_segmentation_qc_issue_marks_auto_flagged(monkeypatch):
    db = MagicMock()
    question = _make_question(review_status="unreviewed")

    def _mock_call(**kwargs):
        schema = kwargs["response_schema"]
        if schema.get("title") == "SegmentationQCV1":
            return {
                "question_id": "q_01JTEST0001",
                "is_complete": False,
                "issues": ["missing_bottom"],
                "confidence": 0.6,
            }
        return _valid_structured(needs_review=False)

    monkeypatch.setattr("app.pipeline.structure_step.call_gemini_structured", _mock_call)
    run_gemini_structuring(db, question)

    assert "segmentation_qc_v1" in question.structure
    assert question.review_status == "auto_flagged"
