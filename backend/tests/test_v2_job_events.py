import time

from app.main import app
from tests.http_client import SyncASGIClient


def _wait_job_events(client: SyncASGIClient, job_id: str, timeout_seconds: float = 3.0) -> list[dict]:
    deadline = time.time() + timeout_seconds
    latest: list[dict] = []
    while time.time() < deadline:
        events_resp = client.get(f"/v2/jobs/{job_id}/events")
        assert events_resp.status_code == 200
        latest = events_resp.json()["events"]
        if latest and latest[-1]["status"] in {"done", "failed"}:
            return latest
        time.sleep(0.05)
    return latest


def test_job_events_contract():
    client = SyncASGIClient(app)

    files = {"file": ("timeline.pdf", b"%PDF-1.4 mock", "application/pdf")}
    created = client.post("/v2/documents", files=files)
    assert created.status_code == 200
    job_id = created.json()["jobId"]

    events = _wait_job_events(client, job_id)
    assert len(events) >= 2
    assert events[0]["status"] == "queued"
    assert events[-1]["status"] in {"done", "failed"}
    assert events[-1]["stage"] in {"completed", "error"}
