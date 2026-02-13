"""Regression guard for removed sets.needs_review_count usage."""

from pathlib import Path


def test_backend_app_has_no_needs_review_count_reference():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []

    for path in app_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        if "needs_review_count" in content:
            offenders.append(str(path.relative_to(app_dir.parent)))

    assert offenders == [], f"Unexpected needs_review_count references: {offenders}"
