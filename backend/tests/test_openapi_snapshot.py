import json
from pathlib import Path

from app.main import app


def test_openapi_contains_required_paths_snapshot():
    snapshot_path = Path(__file__).parent / "snapshots" / "openapi_required_paths.json"
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))

    schema = app.openapi()
    actual_paths = set(schema.get("paths", {}).keys())

    for required_path in expected["requiredPaths"]:
        assert required_path in actual_paths
