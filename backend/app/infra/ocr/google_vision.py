from __future__ import annotations

from typing import Any

from app.infra.ports.ocr import OCRPort


def _vertices_to_bbox(vertices: list[Any] | None) -> dict[str, int]:
    if not vertices:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    xs = [int(getattr(v, "x", 0) or 0) for v in vertices]
    ys = [int(getattr(v, "y", 0) or 0) for v in vertices]
    return {
        "x1": min(xs) if xs else 0,
        "y1": min(ys) if ys else 0,
        "x2": max(xs) if xs else 0,
        "y2": max(ys) if ys else 0,
    }


class GoogleVisionOCR(OCRPort):
    provider_name = "google_vision"

    def __init__(self, *, language_hints: list[str] | None = None, timeout_seconds: int = 30):
        try:
            from google.cloud import vision  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("google-cloud-vision package is not installed") from exc

        self._vision = vision
        self._client = vision.ImageAnnotatorClient()
        self.language_hints = [item.strip() for item in (language_hints or []) if item and item.strip()]
        self.timeout_seconds = max(3, int(timeout_seconds))

    def extract(self, image_bytes: bytes) -> dict[str, Any]:
        image = self._vision.Image(content=image_bytes)
        kwargs: dict[str, Any] = {"image": image, "timeout": self.timeout_seconds}
        if self.language_hints:
            kwargs["image_context"] = self._vision.ImageContext(language_hints=self.language_hints)

        response = self._client.document_text_detection(**kwargs)
        if getattr(response, "error", None) and response.error.message:
            raise RuntimeError(f"Google Vision OCR error: {response.error.message}")

        annotation = response.full_text_annotation
        text = ""
        tokens: list[dict[str, Any]] = []
        confidences: list[float] = []

        if annotation:
            text = (annotation.text or "").strip()
            for page in annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = "".join(getattr(sym, "text", "") for sym in word.symbols).strip()
                            if not word_text:
                                continue
                            confidence = float(getattr(word, "confidence", 0.0) or 0.0)
                            confidences.append(confidence)
                            bbox = _vertices_to_bbox(getattr(word.bounding_box, "vertices", None))
                            tokens.append(
                                {
                                    "text": word_text,
                                    "bbox": bbox,
                                    "conf": confidence,
                                }
                            )

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return {
            "text": text,
            "confidence": avg_confidence,
            "tokens": tokens,
        }
