"""Tests for Gemini JSON schemas and validation helpers."""

import pytest

from app.gemini.validate import (
    SchemaValidationError,
    validate_question_structure,
    validate_segmentation_qc,
)


# ── Fixtures ────────────────────────────────────────────────────────


VALID_QUESTION_STRUCTURE = {
    "question_id": "q_01JTEST0001",
    "question_format": "multiple_choice",
    "stem": "다음 중 에너지 전환의 예로 옳은 것은?",
    "materials": [
        {"kind": "passage", "text": "에너지는 한 형태에서 다른 형태로 전환될 수 있다."}
    ],
    "choices": [
        {"label": "1", "text": "전구: 전기 에너지 → 빛 에너지"},
        {"label": "2", "text": "광합성: 빛 에너지 → 화학 에너지"},
        {"label": "3", "text": "선풍기: 전기 에너지 → 운동 에너지"},
        {"label": "4", "text": "위의 모두"},
    ],
    "asset_links": [
        {
            "asset_id": "a_01JTEST0001",
            "asset_type": "diagram",
            "attach_to": "stem",
            "rationale": "에너지 전환 다이어그램이 문제 지문에 포함됨",
        }
    ],
    "review": {
        "needs_review": False,
        "flags": [],
        "evidence_summary": "All OCR tokens have confidence > 0.9",
    },
    "clean_text_preview": "다음 중 에너지 전환의 예로 옳은 것은? 1) 전구 2) 광합성 3) 선풍기 4) 위의 모두",
}

VALID_SEGMENTATION_QC = {
    "question_id": "q_01JTEST0001",
    "is_complete": True,
    "issues": [],
    "confidence": 0.95,
}


# ── QuestionStructureV1 ─────────────────────────────────────────────


class TestQuestionStructureValidation:
    def test_valid_passes(self):
        result = validate_question_structure(VALID_QUESTION_STRUCTURE)
        assert result.question_id == "q_01JTEST0001"
        assert result.question_format.value == "multiple_choice"
        assert len(result.choices) == 4
        assert result.review.needs_review is False

    def test_missing_required_field_fails(self):
        invalid = {**VALID_QUESTION_STRUCTURE}
        del invalid["stem"]
        with pytest.raises(SchemaValidationError, match="stem"):
            validate_question_structure(invalid)

    def test_invalid_enum_fails(self):
        invalid = {**VALID_QUESTION_STRUCTURE, "question_format": "essay"}
        with pytest.raises(SchemaValidationError):
            validate_question_structure(invalid)

    def test_extra_property_fails(self):
        invalid = {**VALID_QUESTION_STRUCTURE, "extra_field": "bad"}
        with pytest.raises(SchemaValidationError):
            validate_question_structure(invalid)


# ── SegmentationQCV1 ────────────────────────────────────────────────


class TestSegmentationQCValidation:
    def test_valid_passes(self):
        result = validate_segmentation_qc(VALID_SEGMENTATION_QC)
        assert result.question_id == "q_01JTEST0001"
        assert result.is_complete is True
        assert result.confidence == 0.95

    def test_valid_with_optional_fields(self):
        data = {
            **VALID_SEGMENTATION_QC,
            "suggested_bbox_adjustment": {"dx": -5, "dy": 0, "dw": 10, "dh": 5},
            "notes": "약간 왼쪽이 잘림",
        }
        result = validate_segmentation_qc(data)
        assert result.suggested_bbox_adjustment is not None
        assert result.suggested_bbox_adjustment.dx == -5
        assert result.notes == "약간 왼쪽이 잘림"

    def test_missing_required_field_fails(self):
        invalid = {**VALID_SEGMENTATION_QC}
        del invalid["confidence"]
        with pytest.raises(SchemaValidationError, match="confidence"):
            validate_segmentation_qc(invalid)

    def test_confidence_out_of_range_fails(self):
        invalid = {**VALID_SEGMENTATION_QC, "confidence": 1.5}
        with pytest.raises(SchemaValidationError):
            validate_segmentation_qc(invalid)

    def test_invalid_issue_enum_fails(self):
        invalid = {**VALID_SEGMENTATION_QC, "issues": ["nonexistent_issue"]}
        with pytest.raises(SchemaValidationError):
            validate_segmentation_qc(invalid)
