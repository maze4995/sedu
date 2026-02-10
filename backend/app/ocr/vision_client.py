"""Google Cloud Vision DOCUMENT_TEXT_DETECTION wrapper.

Returns a normalised dict with full_text, pages/blocks/paragraphs/words
hierarchy, and avg_confidence.
"""

from __future__ import annotations

from typing import Any

from google.cloud import vision


def _vertices_to_bbox(vertices: Any) -> dict[str, int]:
    """Convert Vision BoundingPoly vertices to {x1, y1, x2, y2}.

    Vertices are ordered: top-left, top-right, bottom-right, bottom-left.
    Some vertices may lack x/y attributes, so we default to 0.
    """
    xs = [getattr(v, "x", 0) or 0 for v in vertices]
    ys = [getattr(v, "y", 0) or 0 for v in vertices]
    return {
        "x1": min(xs),
        "y1": min(ys),
        "x2": max(xs),
        "y2": max(ys),
    }


def _extract_word_text(word: Any) -> str:
    """Concatenate symbol texts in a word."""
    return "".join(
        symbol.text for symbol in word.symbols if symbol.text
    )


def normalize_response(response: Any) -> dict:
    """Convert a Vision AnnotateImageResponse into a clean dict.

    This is a pure function (no network calls) so it's easy to unit-test
    with mocked response objects.
    """
    annotation = response.full_text_annotation
    if not annotation or not annotation.pages:
        return {
            "full_text": "",
            "pages": [],
            "avg_confidence": None,
        }

    all_confidences: list[float] = []
    pages_out: list[dict] = []

    for page in annotation.pages:
        blocks_out: list[dict] = []
        for block in page.blocks:
            paragraphs_out: list[dict] = []
            for paragraph in block.paragraphs:
                words_out: list[dict] = []
                for word in paragraph.words:
                    text = _extract_word_text(word)
                    conf: float | None = None
                    if hasattr(word, "confidence") and word.confidence:
                        conf = round(word.confidence, 4)
                        all_confidences.append(word.confidence)

                    bbox = _vertices_to_bbox(word.bounding_box.vertices)
                    words_out.append({
                        "text": text,
                        "confidence": conf,
                        "bbox": bbox,
                    })
                paragraphs_out.append({"words": words_out})
            blocks_out.append({"paragraphs": paragraphs_out})
        pages_out.append({"blocks": blocks_out})

    avg_conf: float | None = None
    if all_confidences:
        avg_conf = round(sum(all_confidences) / len(all_confidences), 4)

    return {
        "full_text": annotation.text or "",
        "pages": pages_out,
        "avg_confidence": avg_conf,
    }


class VisionOCRClient:
    """Thin wrapper around Cloud Vision DOCUMENT_TEXT_DETECTION."""

    def __init__(self) -> None:
        self._client = vision.ImageAnnotatorClient()

    def ocr_document_bytes(self, image_bytes: bytes) -> dict:
        """Run DOCUMENT_TEXT_DETECTION on raw image bytes.

        Returns the normalised dict produced by ``normalize_response``.
        """
        image = vision.Image(content=image_bytes)
        response = self._client.document_text_detection(image=image)

        if response.error and response.error.message:
            raise RuntimeError(
                f"Vision API error: {response.error.message}"
            )

        return normalize_response(response)
