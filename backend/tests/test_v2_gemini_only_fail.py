import time

from app.api.v2 import dependencies
from app.core.config import get_settings
from app.main import app
from tests.http_client import SyncASGIClient


def _clear_caches() -> None:
    get_settings.cache_clear()
    dependencies.get_store.cache_clear()
    dependencies.get_storage.cache_clear()
    dependencies.get_ocr.cache_clear()
    dependencies.get_llm.cache_clear()


def _wait_terminal(client: SyncASGIClient, job_id: str, timeout_seconds: float = 3.0) -> dict:
    deadline = time.time() + timeout_seconds
    latest = {}
    while time.time() < deadline:
        resp = client.get(f"/v2/jobs/{job_id}")
        assert resp.status_code == 200
        latest = resp.json()
        if latest.get("status") in {"done", "failed"}:
            return latest
        time.sleep(0.05)
    return latest


def test_gemini_full_mode_fails_job_instead_of_ocr_fallback(monkeypatch):
    monkeypatch.setenv("SEDU_EXTRACTION_MODE", "gemini_full")
    monkeypatch.setenv("SEDU_LLM_BACKEND", "mock")
    _clear_caches()

    try:
        client = SyncASGIClient(app)
        created = client.post(
            "/v2/documents",
            files={"file": ("sample.pdf", b"%PDF-1.4 mock", "application/pdf")},
        )
        assert created.status_code == 200
        body = created.json()

        job = _wait_terminal(client, body["jobId"])
        assert job["status"] == "failed"
        assert job["stage"] == "error"
        assert "gemini_full mode requires a multimodal LLM backend" in (job.get("errorMessage") or "")

        questions = client.get(f"/v2/sets/{body['setId']}/questions")
        assert questions.status_code == 200
        assert questions.json()["questions"] == []
    finally:
        _clear_caches()
