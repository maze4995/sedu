"""OCR step: run Vision OCR on a question crop and persist results."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.question import Question
from app.ocr.vision_client import VisionOCRClient

logger = logging.getLogger(__name__)

_AUTO_OK_THRESHOLD = 0.85


def _flatten_tokens(pages: list[dict]) -> list[dict]:
    """Flatten pages/blocks/paragraphs/words into a simple token list.

    Returns:
        [{"text": "...", "bbox": {x1,y1,x2,y2}, "conf": 0.93}, ...]
    """
    tokens: list[dict] = []
    for page in pages:
        for block in page.get("blocks", []):
            for para in block.get("paragraphs", []):
                for word in para.get("words", []):
                    tokens.append({
                        "text": word["text"],
                        "bbox": word["bbox"],
                        "conf": word["confidence"],
                    })
    return tokens


def run_ocr_for_question(
    db: Session,
    question: Question,
    image_bytes: bytes,
    *,
    client: VisionOCRClient | None = None,
) -> None:
    """Run Vision OCR on a question crop image and persist results.

    Updates:
        - question.ocr_text          = full_text
        - question.confidence         = avg_confidence
        - question.structure          += {"ocr_tokens": [...]}
        - question.metadata           += {"ocr_avg_confidence": ...}
        - question.review_status      = auto_ok | auto_flagged
    """
    if client is None:
        client = VisionOCRClient()

    result = client.ocr_document_bytes(image_bytes)

    question.ocr_text = result["full_text"]

    avg_conf = result["avg_confidence"]
    question.confidence = avg_conf

    # Merge into structure (preserve existing keys).
    structure = dict(question.structure) if question.structure else {}
    structure["ocr_tokens"] = _flatten_tokens(result["pages"])
    question.structure = structure

    # Merge into metadata.
    meta = dict(question.metadata_json) if question.metadata_json else {}
    meta["ocr_avg_confidence"] = avg_conf
    question.metadata_json = meta

    # Review status based on confidence.
    if avg_conf is not None and avg_conf >= _AUTO_OK_THRESHOLD:
        question.review_status = "auto_ok"
    else:
        question.review_status = "auto_flagged"

    db.add(question)
    db.commit()
    db.refresh(question)

    logger.info(
        "OCR complete for %s: %d chars, avg_conf=%.3f, status=%s",
        question.public_id,
        len(question.ocr_text or ""),
        avg_conf or 0,
        question.review_status,
    )
