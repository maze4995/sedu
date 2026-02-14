from app.main import app
from tests.http_client import SyncASGIClient


def test_healthz_200():
    client = SyncASGIClient(app)
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"ok": "true"}
