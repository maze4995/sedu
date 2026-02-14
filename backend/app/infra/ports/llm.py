from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMPort(ABC):
    @abstractmethod
    def generate_structured(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Return schema-constrained JSON output."""

    def generate_structured_from_media(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        media_bytes: bytes,
        media_mime_type: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Optional multimodal structured generation. Providers may override."""
        raise NotImplementedError("This LLM provider does not support media input.")
