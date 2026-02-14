from __future__ import annotations

import io
import time

from PIL import Image, ImageDraw

from app.core.config import get_settings
from app.main import app
from app.workers.extraction.cropper import QuestionCropper
from app.workers.extraction.pipeline import DocumentExtractionPipeline
from tests.http_client import SyncASGIClient


def _make_sample_image() -> bytes:
    image = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 80), "1. first question", fill="black")
    draw.text((40, 220), "1) A 2) B 3) C", fill="black")
    draw.text((40, 480), "2. second question", fill="black")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _wait_questions(client: SyncASGIClient, set_id: str, timeout_seconds: float = 3.0):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        resp = client.get(f"/v2/sets/{set_id}/questions")
        assert resp.status_code == 200
        items = resp.json()["questions"]
        if items:
            return items
        time.sleep(0.05)
    return []


def test_question_crop_url_contract(monkeypatch):
    monkeypatch.setattr(
        DocumentExtractionPipeline,
        "_extract_image",
        lambda self, payload: ("1. first question\n2. second question", 0.9, "mock_image"),
    )
    monkeypatch.setattr(
        QuestionCropper,
        "_detect_question_starts",
        lambda self, image: [],
    )

    client = SyncASGIClient(app)
    payload = _make_sample_image()

    created = client.post(
        "/v2/documents",
        files={"file": ("crop.png", payload, "image/png")},
    )
    assert created.status_code == 200
    set_id = created.json()["setId"]

    questions = _wait_questions(client, set_id)
    assert questions
    first = questions[0]
    assert first.get("croppedImageUrl")
    assert str(first["croppedImageUrl"]).startswith("/uploads/")

    detail = client.get(f"/v2/questions/{first['questionId']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body.get("croppedImageUrl")

    cropped_url = str(body["croppedImageUrl"])
    assert cropped_url.startswith("/uploads/")
    relative_key = cropped_url.removeprefix("/uploads/")
    crop_path = get_settings().upload_dir / relative_key
    assert crop_path.exists()
    assert crop_path.read_bytes().startswith(b"\x89PNG")
