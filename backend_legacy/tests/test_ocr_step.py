"""Tests for run_ocr_for_question with a mocked VisionOCRClient."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.pipeline.ocr_step import run_ocr_for_question, _flatten_tokens


# ── helpers ──────────────────────────────────────────────────────────


def _make_question(**overrides):
    """Create a minimal Question-like object with writable attributes."""
    defaults = {
        "public_id": f"q_{uuid.uuid4().hex[:12]}",
        "set_id": uuid.uuid4(),
        "order_index": 1,
        "number_label": "1",
        "ocr_text": None,
        "structure": None,
        "metadata_json": None,
        "confidence": None,
        "review_status": "unreviewed",
    }
    defaults.update(overrides)

    q = MagicMock()
    for k, v in defaults.items():
        setattr(q, k, v)
    return q


def _make_mock_client(full_text: str, pages: list[dict], avg_confidence: float | None):
    """Build a mock VisionOCRClient that returns the given normalized dict."""
    client = MagicMock()
    client.ocr_document_bytes.return_value = {
        "full_text": full_text,
        "pages": pages,
        "avg_confidence": avg_confidence,
    }
    return client


def _simple_pages(words: list[dict]) -> list[dict]:
    """Wrap a flat word list in the pages/blocks/paragraphs hierarchy."""
    return [{"blocks": [{"paragraphs": [{"words": words}]}]}]


# ── Tests ────────────────────────────────────────────────────────────


class TestRunOcrForQuestion:
    def test_stores_ocr_text(self):
        db = MagicMock()
        q = _make_question()
        words = [
            {"text": "다음", "bbox": {"x1": 0, "y1": 0, "x2": 50, "y2": 20}, "confidence": 0.95},
        ]
        client = _make_mock_client("다음", _simple_pages(words), 0.95)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.ocr_text == "다음"

    def test_stores_tokens_in_structure(self):
        db = MagicMock()
        q = _make_question()
        words = [
            {"text": "A", "bbox": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}, "confidence": 0.9},
            {"text": "B", "bbox": {"x1": 15, "y1": 0, "x2": 25, "y2": 10}, "confidence": 0.8},
        ]
        client = _make_mock_client("A B", _simple_pages(words), 0.85)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert "ocr_tokens" in q.structure
        assert len(q.structure["ocr_tokens"]) == 2
        assert q.structure["ocr_tokens"][0]["text"] == "A"

    def test_confidence_updated(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.92)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.confidence == 0.92

    def test_metadata_stores_avg_confidence(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.88)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.metadata_json["ocr_avg_confidence"] == 0.88
        assert q.metadata_json["ocr_source"] == "crop_vision"

    def test_review_status_auto_ok_above_threshold(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.90)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.review_status == "auto_ok"

    def test_review_status_auto_flagged_below_threshold(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.70)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.review_status == "auto_flagged"

    def test_review_status_auto_ok_at_exact_threshold(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.85)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.review_status == "auto_ok"

    def test_review_status_auto_flagged_when_none(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("", [], None)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.review_status == "auto_flagged"

    def test_preserves_existing_structure_keys(self):
        db = MagicMock()
        q = _make_question(structure={"existing_key": "value"})
        client = _make_mock_client("text", _simple_pages([]), 0.90)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.structure["existing_key"] == "value"
        assert "ocr_tokens" in q.structure

    def test_preserves_existing_metadata_keys(self):
        db = MagicMock()
        q = _make_question(metadata_json={"source": "test"})
        client = _make_mock_client("text", _simple_pages([]), 0.90)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        assert q.metadata_json["source"] == "test"
        assert q.metadata_json["ocr_avg_confidence"] == 0.90

    def test_db_commit_called(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.90)

        run_ocr_for_question(db, q, b"fake-image", client=client)

        db.add.assert_called_once_with(q)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(q)

    def test_vision_client_called_with_image_bytes(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.90)

        run_ocr_for_question(db, q, b"my-png-bytes", client=client)

        client.ocr_document_bytes.assert_called_once_with(b"my-png-bytes")

    def test_commit_can_be_deferred(self):
        db = MagicMock()
        q = _make_question()
        client = _make_mock_client("text", _simple_pages([]), 0.90)

        run_ocr_for_question(db, q, b"fake-image", client=client, commit=False)

        db.add.assert_called_once_with(q)
        db.commit.assert_not_called()
        db.refresh.assert_not_called()
