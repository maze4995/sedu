from __future__ import annotations

from abc import ABC, abstractmethod


class StoragePort(ABC):
    @abstractmethod
    def save_bytes(self, key: str, data: bytes, content_type: str | None) -> str:
        """Persist bytes and return a retrievable URL or path."""

    @abstractmethod
    def build_url(self, key: str) -> str:
        """Resolve a public URL (or local path) for a key."""
