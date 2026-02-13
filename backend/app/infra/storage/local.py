from __future__ import annotations

from pathlib import Path

from app.infra.ports.storage import StoragePort


class LocalFileStorage(StoragePort):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, key: str, data: bytes, content_type: str | None) -> str:
        dest = self.base_dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return self.build_url(key)

    def build_url(self, key: str) -> str:
        return f"/uploads/{key}"
