from __future__ import annotations

from app.infra.ports.storage import StoragePort


class S3Storage(StoragePort):
    """Placeholder adapter for production object storage."""

    def __init__(self, bucket: str, region: str | None):
        self.bucket = bucket
        self.region = region

    def save_bytes(self, key: str, data: bytes, content_type: str | None) -> str:
        raise NotImplementedError("S3 adapter is not implemented in Sprint 1")

    def build_url(self, key: str) -> str:
        if self.region:
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"
