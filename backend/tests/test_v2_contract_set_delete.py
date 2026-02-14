from app.main import app
from tests.http_client import SyncASGIClient


def _create_set(client: SyncASGIClient) -> tuple[str, str]:
    created = client.post("/v2/documents", files={"file": ("delete.pdf", b"%PDF-1.4", "application/pdf")})
    assert created.status_code == 200
    body = created.json()
    return body["setId"], body["jobId"]


def test_delete_set_contract():
    client = SyncASGIClient(app)
    set_id, job_id = _create_set(client)

    deleted = client.delete(f"/v2/sets/{set_id}")
    assert deleted.status_code == 200
    deleted_body = deleted.json()
    assert deleted_body["ok"] is True
    assert deleted_body["setId"] == set_id

    get_set = client.get(f"/v2/sets/{set_id}")
    assert get_set.status_code == 404

    get_questions = client.get(f"/v2/sets/{set_id}/questions")
    assert get_questions.status_code == 404

    job_resp = client.get(f"/v2/jobs/{job_id}")
    assert job_resp.status_code == 404


def test_delete_set_404_contract():
    client = SyncASGIClient(app)
    resp = client.delete("/v2/sets/set_not_exists")
    assert resp.status_code == 404
