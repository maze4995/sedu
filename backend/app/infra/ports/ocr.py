from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class OCRPort(ABC):
    @abstractmethod
    def extract(self, image_bytes: bytes) -> dict[str, Any]:
        """Return normalized OCR payload for one image."""
