from fastapi.testclient import TestClient

from app.main import app


def test_job_events_contract():
    client = TestClient(app)

    files = {"file": ("timeline.pdf", b"%PDF-1.4 mock", "application/pdf")}
    created = client.post("/v2/documents", files=files)
    assert created.status_code == 200
    job_id = created.json()["jobId"]

    events_resp = client.get(f"/v2/jobs/{job_id}/events")
    assert events_resp.status_code == 200
    body = events_resp.json()

    assert body["jobId"] == job_id
    assert len(body["events"]) >= 2
    assert body["events"][0]["status"] == "queued"
    assert body["events"][-1]["status"] in {"done", "failed"}
    assert body["events"][-1]["stage"] in {"completed", "error"}
