"""Tests for question number detection and bbox construction."""

import pytest

from app.pipeline.layout import (
    build_question_bboxes,
    detect_question_anchors,
    detect_question_anchors_with_page,
    is_question_number,
)


# ── is_question_number ──────────────────────────────────────────────


class TestIsQuestionNumber:
    @pytest.mark.parametrize("text", [
        "1.", "2.", "10.", "99.",          # dot
        "3)", "12)",                       # paren
        "(4)", "(15)",                     # wrapped paren
        "[5]", "[20]",                     # bracket
        "6", "17",                         # bare number
    ])
    def test_valid_patterns(self, text: str):
        assert is_question_number(text) is True

    @pytest.mark.parametrize("text", [
        "100.",          # 3 digits
        "abc",
        "1.2",
        "",
        " ",
        "문제1",
        "(A)",
        "1. 다음",       # trailing text
        "Q1",
    ])
    def test_invalid_patterns(self, text: str):
        assert is_question_number(text) is False


# ── detect_question_anchors ─────────────────────────────────────────


def _tok(text: str, y1: int, x1: int = 0) -> dict:
    return {
        "text": text,
        "bbox": {"x1": x1, "y1": y1, "x2": x1 + 20, "y2": y1 + 15},
        "conf": 0.95,
    }


class TestDetectQuestionAnchors:
    def test_basic_detection(self):
        tokens = [
            _tok("다음", 10),
            _tok("1.", 50),
            _tok("문제", 55),
            _tok("2.", 200),
            _tok("풀이", 210),
            _tok("3.", 400),
        ]
        anchors = detect_question_anchors(tokens)
        assert len(anchors) == 3
        assert [a["number_label"] for a in anchors] == ["1", "2", "3"]

    def test_sorted_by_y(self):
        tokens = [
            _tok("3.", 400),
            _tok("1.", 50),
            _tok("2.", 200),
        ]
        anchors = detect_question_anchors(tokens)
        assert [a["number_label"] for a in anchors] == ["1", "2", "3"]

    def test_deduplication(self):
        tokens = [
            _tok("1.", 50, x1=0),
            _tok("1.", 55, x1=30),   # duplicate, close y
            _tok("2.", 200),
        ]
        anchors = detect_question_anchors(tokens)
        assert len(anchors) == 2

    def test_no_anchors(self):
        tokens = [
            _tok("다음", 10),
            _tok("문제를", 30),
            _tok("풀어라", 50),
        ]
        assert detect_question_anchors(tokens) == []

    def test_bracket_and_paren_formats(self):
        tokens = [
            _tok("(1)", 50),
            _tok("[2]", 200),
            _tok("3)", 400),
        ]
        anchors = detect_question_anchors(tokens)
        assert len(anchors) == 3
        assert [a["number_label"] for a in anchors] == ["1", "2", "3"]

    def test_filters_header_footer_number_noise(self):
        tokens = [
            _tok("1", 10),      # likely page header/footer noise
            _tok("1.", 120),    # real question start
            _tok("2.", 320),
            _tok("3", 980),     # likely footer page number
        ]
        anchors = detect_question_anchors_with_page(tokens, page_height=1000)
        assert [a["number_label"] for a in anchors] == ["1", "2"]


# ── build_question_bboxes ──────────────────────────────────────────


class TestBuildQuestionBboxes:
    def test_basic_bboxes(self):
        anchors = [
            {"text": "1.", "bbox": {"x1": 10, "y1": 100, "x2": 30, "y2": 115}, "conf": 0.9, "number_label": "1"},
            {"text": "2.", "bbox": {"x1": 10, "y1": 400, "x2": 30, "y2": 415}, "conf": 0.9, "number_label": "2"},
            {"text": "3.", "bbox": {"x1": 10, "y1": 700, "x2": 30, "y2": 715}, "conf": 0.9, "number_label": "3"},
        ]
        bboxes = build_question_bboxes(anchors, page_width=800, page_height=1000)

        assert len(bboxes) == 3

        # First question: top = 100 - margin, bottom = 400 - margin
        assert bboxes[0]["x1"] == 0
        assert bboxes[0]["x2"] == 800
        assert bboxes[0]["y1"] == 92   # 100 - 8
        assert bboxes[0]["y2"] == 396  # 400 - 4
        assert bboxes[0]["number_label"] == "1"

        # Last question goes to page bottom.
        assert bboxes[2]["y2"] == 1000

    def test_empty_anchors(self):
        assert build_question_bboxes([], 800, 1000) == []

    def test_single_anchor(self):
        anchors = [
            {"text": "1.", "bbox": {"x1": 10, "y1": 50, "x2": 30, "y2": 65}, "conf": 0.9, "number_label": "1"},
        ]
        bboxes = build_question_bboxes(anchors, 800, 1200)
        assert len(bboxes) == 1
        assert bboxes[0]["y1"] == 42   # 50 - 8
        assert bboxes[0]["y2"] == 1200

    def test_top_margin_clamp(self):
        anchors = [
            {"text": "1.", "bbox": {"x1": 10, "y1": 3, "x2": 30, "y2": 18}, "conf": 0.9, "number_label": "1"},
        ]
        bboxes = build_question_bboxes(anchors, 800, 1000)
        assert bboxes[0]["y1"] == 0  # clamped to 0
