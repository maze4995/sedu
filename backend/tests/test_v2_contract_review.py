import time

from fastapi.testclient import TestClient

from app.main import app


def _create_set_and_question(client: TestClient) -> tuple[str, str]:
    files = {"file": ("sample.png", b"mock-image", "image/png")}
    created = client.post("/v2/documents", files=files).json()
    set_id = created["setId"]

    deadline = time.time() + 2.0
    while time.time() < deadline:
        q_resp = client.get(f"/v2/sets/{set_id}/questions")
        assert q_resp.status_code == 200
        questions = q_resp.json()["questions"]
        if questions:
            return set_id, questions[0]["questionId"]
        time.sleep(0.05)

    raise AssertionError("Timed out waiting for extracted questions")


def test_review_queue_and_patch_contract():
    client = TestClient(app)
    _, question_id = _create_set_and_question(client)

    reprocess = client.post(f"/v2/questions/{question_id}/reprocess")
    assert reprocess.status_code == 200
    assert reprocess.json()["questionId"] == question_id

    queue = client.get("/v2/review/queue")
    assert queue.status_code == 200
    queue_body = queue.json()
    assert "items" in queue_body
    assert queue_body["count"] >= 1

    patch = client.patch(
        f"/v2/questions/{question_id}/review",
        json={
            "reviewer": "teacher_1",
            "reviewStatus": "approved",
            "note": "검수 완료",
            "metadataPatch": {"difficulty": "상"},
        },
    )
    assert patch.status_code == 200
    patch_body = patch.json()
    assert patch_body["questionId"] == question_id
    assert patch_body["reviewStatus"] == "approved"
    assert patch_body["metadata"]["difficulty"] == "상"
