from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMPort(ABC):
    @abstractmethod
    def generate_structured(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return schema-constrained JSON output."""
