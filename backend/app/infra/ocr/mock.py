from __future__ import annotations

from typing import Any

from app.infra.ports.ocr import OCRPort


class MockOCR(OCRPort):
    def extract(self, image_bytes: bytes) -> dict[str, Any]:
        size_hint = max(1, len(image_bytes) // 256)
        return {
            "text": "[mock] OCR text",
            "confidence": 0.91,
            "tokens": [
                {
                    "text": "mock",
                    "bbox": {"x1": 0, "y1": 0, "x2": 20 * size_hint, "y2": 20},
                    "conf": 0.91,
                }
            ],
        }
