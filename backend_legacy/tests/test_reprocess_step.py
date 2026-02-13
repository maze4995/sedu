"""Tests for question reprocess pipeline step."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.pipeline.reprocess_step import reprocess_question


def test_reprocess_question_updates_structuring_metadata(monkeypatch, tmp_path):
    uploads_root = tmp_path / "uploads"
    crop_rel = "set_test/crops/q_test.png"
    crop_path = uploads_root / crop_rel
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    crop_path.write_bytes(b"fake-png")

    question = SimpleNamespace(
        public_id="q_test",
        cropped_image_key=crop_rel,
        metadata_json={},
        review_status="unreviewed",
        set=SimpleNamespace(file_key=None),
    )

    monkeypatch.setattr("app.pipeline.reprocess_step.uploads_dir", lambda: uploads_root)
    monkeypatch.setattr(
        "app.pipeline.reprocess_step.run_ocr_for_question",
        lambda db, q, image_bytes: setattr(q, "ocr_text", "ocr refreshed"),
    )
    monkeypatch.setattr(
        "app.pipeline.reprocess_step.run_gemini_structuring",
        lambda db, q: q.metadata_json.update({"structured_at": "2026-02-13T00:00:00+00:00"}),
    )
    monkeypatch.setattr("app.pipeline.reprocess_step._sync_set_status", lambda db, q: None)

    reprocess_question(MagicMock(), question)

    assert question.ocr_text == "ocr refreshed"
    assert question.metadata_json["structured_at"] == "2026-02-13T00:00:00+00:00"
