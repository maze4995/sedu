import time

from app.main import app
from tests.http_client import SyncASGIClient


def _create_question(client: SyncASGIClient) -> str:
    created = client.post("/v2/documents", files={"file": ("sample.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert created.status_code == 200
    set_id = created.json()["setId"]

    deadline = time.time() + 2.0
    while time.time() < deadline:
        resp = client.get(f"/v2/sets/{set_id}/questions")
        assert resp.status_code == 200
        items = resp.json()["questions"]
        if items:
            return items[0]["questionId"]
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for question extraction")


def test_hint_and_variant_contract():
    client = SyncASGIClient(app)
    question_id = _create_question(client)

    hint = client.post(
        f"/v2/questions/{question_id}/hint",
        json={
            "level": "weak",
            "recentChat": [{"role": "user", "text": "어떻게 시작하죠?"}],
            "strokeSummary": "",
        },
    )
    assert hint.status_code == 200
    hint_body = hint.json()
    assert hint_body["questionId"] == question_id
    assert isinstance(hint_body["hint"], str)
    assert hint_body["hint"]

    listed_before = client.get(f"/v2/questions/{question_id}/variants")
    assert listed_before.status_code == 200
    assert isinstance(listed_before.json()["variants"], list)

    created = client.post(
        f"/v2/questions/{question_id}/variants",
        json={"variantType": "paraphrase"},
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["questionId"] == question_id
    assert created_body["variant"]["variantType"] == "paraphrase"

    listed_after = client.get(f"/v2/questions/{question_id}/variants")
    assert listed_after.status_code == 200
    after_body = listed_after.json()
    assert after_body["questionId"] == question_id
    assert len(after_body["variants"]) >= 1
