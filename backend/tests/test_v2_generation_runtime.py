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


def test_variant_saved_and_hint_has_model():
    client = SyncASGIClient(app)
    question_id = _create_question(client)

    create_resp = client.post(
        f"/v2/questions/{question_id}/variants",
        json={"variantType": "paraphrase"},
    )
    assert create_resp.status_code == 200
    created = create_resp.json()["variant"]
    assert created["variantId"].startswith("var_")

    list_resp = client.get(f"/v2/questions/{question_id}/variants")
    assert list_resp.status_code == 200
    listed = list_resp.json()["variants"]
    assert listed
    assert any(item["variantId"] == created["variantId"] for item in listed)

    hint_resp = client.post(
        f"/v2/questions/{question_id}/hint",
        json={"level": "medium", "recentChat": [], "strokeSummary": ""},
    )
    assert hint_resp.status_code == 200
    hint = hint_resp.json()
    assert isinstance(hint["hint"], str) and hint["hint"]
    assert isinstance(hint["model"], str) and hint["model"]
