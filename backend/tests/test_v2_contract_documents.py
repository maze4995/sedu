import time

from app.main import app
from tests.http_client import SyncASGIClient


def _wait_for_job_terminal(client: SyncASGIClient, job_id: str, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    latest: dict = {}
    while time.time() < deadline:
        resp = client.get(f"/v2/jobs/{job_id}")
        assert resp.status_code == 200
        latest = resp.json()
        if latest["status"] in {"done", "failed"}:
            return latest
        time.sleep(0.05)
    return latest


def test_create_document_contract_and_job_lookup():
    client = SyncASGIClient(app)

    files = {"file": ("sample.pdf", b"%PDF-1.4 mock", "application/pdf")}
    resp = client.post("/v2/documents", files=files)
    assert resp.status_code == 200

    body = resp.json()
    assert set(body.keys()) == {"documentId", "setId", "jobId", "status"}
    assert body["setId"].startswith("set_")
    assert body["jobId"].startswith("job_")

    job_body = _wait_for_job_terminal(client, body["jobId"])
    assert job_body["jobId"] == body["jobId"]
    assert job_body["setId"] == body["setId"]
    assert job_body["status"] == "done"
    assert job_body["percent"] == 100.0

    sets_resp = client.get("/v2/sets?limit=10&offset=0")
    assert sets_resp.status_code == 200
    sets_body = sets_resp.json()
    assert sets_body["limit"] == 10
    assert any(item["setId"] == body["setId"] for item in sets_body["sets"])

    questions_resp = client.get(f"/v2/sets/{body['setId']}/questions")
    assert questions_resp.status_code == 200
    assert len(questions_resp.json()["questions"]) == 1
