"""Question reprocess step: recrop (optional) -> OCR -> Gemini structuring."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.question import Question
from app.pipeline.crop import save_question_image
from app.pipeline.ingest import render_pdf_to_images
from app.pipeline.ocr_step import run_ocr_for_question
from app.pipeline.orchestrator import uploads_dir
from app.pipeline.structure_step import run_gemini_structuring


def _normalize_bbox(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    keys = ("x1", "y1", "x2", "y2")
    if not all(k in value for k in keys):
        return None
    return {k: int(value[k]) for k in keys}


def _recrop_from_source(question: Question) -> bytes | None:
    """Rebuild crop bytes from source file when metadata context exists."""
    set_obj = question.set
    if set_obj is None or not set_obj.file_key:
        return None

    metadata = dict(question.metadata_json or {})
    source_page = metadata.get("source_page")
    bbox = _normalize_bbox(metadata.get("question_bbox"))
    if not isinstance(source_page, int) or bbox is None:
        return None

    src_path = uploads_dir() / set_obj.file_key
    if not src_path.exists():
        return None

    src_bytes = src_path.read_bytes()
    mime = (set_obj.source_mime or "").lower()

    if "pdf" in mime:
        pages = render_pdf_to_images(src_bytes)
        if source_page < 0 or source_page >= len(pages):
            return None
        page_img = pages[source_page]
    else:
        page_img = Image.open(io.BytesIO(src_bytes)).convert("RGB")

    region = page_img.crop((bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]))
    out = io.BytesIO()
    region.save(out, format="PNG")
    crop_bytes = out.getvalue()

    if question.cropped_image_key:
        dest = uploads_dir() / question.cropped_image_key
        save_question_image(region, dest)

    return crop_bytes


def _load_crop_bytes(question: Question) -> bytes:
    if question.cropped_image_key:
        path = uploads_dir() / question.cropped_image_key
        if path.exists():
            return path.read_bytes()

    recropped = _recrop_from_source(question)
    if recropped:
        return recropped

    raise FileNotFoundError("No crop image available for question reprocess")


def _sync_set_status(db: Session, question: Question) -> None:
    set_obj = question.set
    if set_obj is None:
        return

    total_stmt = select(func.count()).select_from(Question).where(Question.set_id == set_obj.id)
    flagged_stmt = (
        select(func.count())
        .select_from(Question)
        .where(Question.set_id == set_obj.id, Question.review_status == "auto_flagged")
    )

    total = int(db.execute(total_stmt).scalar_one() or 0)
    flagged = int(db.execute(flagged_stmt).scalar_one() or 0)

    set_obj.question_count = total
    set_obj.status = "needs_review" if flagged > 0 else "ready"
    db.add(set_obj)
    db.commit()
    db.refresh(set_obj)


def reprocess_question(db: Session, question: Question) -> None:
    """Re-run OCR + structuring for a question and resync set status."""
    crop_bytes = _load_crop_bytes(question)
    run_ocr_for_question(db, question, crop_bytes)
    run_gemini_structuring(db, question)
    _sync_set_status(db, question)
