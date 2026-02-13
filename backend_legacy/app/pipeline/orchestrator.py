"""Real extraction pipeline: PDF → pages → OCR → anchors → crops → DB.

Requires:
- Uploaded file saved to disk (file_key on the Set row).
- GOOGLE_APPLICATION_CREDENTIALS for Vision OCR.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import _get_session_factory
from app.models.extraction_job import ExtractionJob
from app.models.question import Question
from app.models.set import Set
from app.utils.ids import new_public_id

logger = logging.getLogger(__name__)

_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_DEBUG_DIR = Path(__file__).resolve().parent.parent.parent / "debug"
_TOKEN_BBOX_PAD = 2
_LINE_MERGE_GAP_PX = 18
_AUTO_OK_THRESHOLD = 0.85
_MAX_JOB_ERROR_LEN = 800
_MAX_QUESTION_ERROR_LEN = 400
_STRICT_REVIEW_STATUSES = {"approved", "rejected"}


def uploads_dir() -> Path:
    return _UPLOADS_DIR


def _update_job(db: Session, job: ExtractionJob, stage: str, progress: float) -> None:
    job.stage = stage
    job.progress = progress
    db.commit()


def _load_job_and_set(db: Session, job_public_id: str) -> tuple[ExtractionJob, Set] | None:
    stmt = select(ExtractionJob).where(ExtractionJob.public_id == job_public_id)
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        return None
    set_obj = db.get(Set, job.set_id)
    if set_obj is None:
        return None
    return job, set_obj


def _truncate_message(message: str, limit: int) -> str:
    msg = (message or "").strip()
    if len(msg) <= limit:
        return msg
    return msg[:limit] + "..."


def _format_exception(exc: Exception, *, limit: int) -> str:
    return _truncate_message(f"{type(exc).__name__}: {exc}", limit)


def _mark_question_step_error(question: Question, step: str, exc: Exception) -> None:
    """Record per-question processing error without aborting the whole job."""
    metadata: dict[str, Any] = dict(question.metadata_json or {})
    metadata[f"{step}_error"] = {
        "type": type(exc).__name__,
        "message": _truncate_message(str(exc), _MAX_QUESTION_ERROR_LEN),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    question.metadata_json = metadata
    if question.review_status not in _STRICT_REVIEW_STATUSES:
        question.review_status = "auto_flagged"


def _intersects_bbox(a: dict, b: dict, *, pad: int = _TOKEN_BBOX_PAD) -> bool:
    """Return True when two bboxes overlap (with optional padding on b)."""
    ax1, ay1, ax2, ay2 = a["x1"], a["y1"], a["x2"], a["y2"]
    bx1 = b["x1"] - pad
    by1 = b["y1"] - pad
    bx2 = b["x2"] + pad
    by2 = b["y2"] + pad
    return not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)


def _tokens_for_question_bbox(tokens: list[dict], question_bbox: dict) -> list[dict]:
    """Select page OCR tokens that belong to a question bbox."""
    selected: list[dict] = []
    for token in tokens:
        text = str(token.get("text") or "").strip()
        bbox = token.get("bbox")
        if not text or not isinstance(bbox, dict):
            continue
        if _intersects_bbox(bbox, question_bbox):
            selected.append({
                "text": text,
                "bbox": bbox,
                "conf": token.get("conf"),
            })

    selected.sort(key=lambda t: (t["bbox"]["y1"], t["bbox"]["x1"]))
    return selected


def _tokens_to_text(tokens: list[dict]) -> str:
    """Convert sorted OCR tokens to a readable multiline text block."""
    if not tokens:
        return ""

    lines: list[str] = []
    current_line: list[str] = []
    current_y: int | None = None

    for token in sorted(tokens, key=lambda t: (t["bbox"]["y1"], t["bbox"]["x1"])):
        text = str(token.get("text") or "").strip()
        if not text:
            continue

        y = int(token["bbox"]["y1"])
        if current_y is None:
            current_line.append(text)
            current_y = y
            continue

        if abs(y - current_y) <= _LINE_MERGE_GAP_PX:
            current_line.append(text)
        else:
            lines.append(" ".join(current_line).strip())
            current_line = [text]
        current_y = y

    if current_line:
        lines.append(" ".join(current_line).strip())

    return "\n".join(line for line in lines if line).strip()


def _avg_confidence(tokens: list[dict]) -> float | None:
    values = [
        float(token["conf"])
        for token in tokens
        if isinstance(token.get("conf"), (int, float))
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _normalize_question_bbox(bbox: dict) -> dict[str, int]:
    """Normalize question bbox into {x1,y1,x2,y2} integer coordinates."""
    return {
        "x1": int(bbox.get("x1", 0)),
        "y1": int(bbox.get("y1", 0)),
        "x2": int(bbox.get("x2", 0)),
        "y2": int(bbox.get("y2", 0)),
    }


def _build_question_context_metadata(*, source_page: int, bbox: dict) -> dict[str, Any]:
    """Persist stable context used by structuring and manual retries."""
    return {
        "source_page": int(source_page),
        "question_bbox": _normalize_question_bbox(bbox),
    }


def _apply_page_ocr_to_question(question: Question, page_tokens: list[dict], bbox: dict) -> None:
    """Populate question OCR fields from already available page OCR tokens."""
    q_tokens = _tokens_for_question_bbox(page_tokens, bbox)
    q_text = _tokens_to_text(q_tokens)
    avg_conf = _avg_confidence(q_tokens)

    question.ocr_text = q_text
    question.confidence = avg_conf

    structure = dict(question.structure) if question.structure else {}
    structure["ocr_tokens"] = q_tokens
    question.structure = structure

    metadata = dict(question.metadata_json) if question.metadata_json else {}
    metadata["ocr_avg_confidence"] = avg_conf
    metadata["ocr_source"] = "page_tokens"
    question.metadata_json = metadata

    if q_text and avg_conf is not None and avg_conf >= _AUTO_OK_THRESHOLD:
        question.review_status = "auto_ok"
    else:
        question.review_status = "auto_flagged"


_CREDENTIALS_DIR = Path(__file__).resolve().parent.parent.parent / "credentials"


def _ensure_credentials() -> str | None:
    """Return path to a valid service-account JSON, or None.

    Priority:
    1. GOOGLE_APPLICATION_CREDENTIALS env var (already set by user).
    2. Auto-discover ``backend/credentials/service-account.json``.
    """
    env_val = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_val and os.path.isfile(env_val):
        return env_val

    # Auto-discover from project credentials/ dir.
    fallback = _CREDENTIALS_DIR / "service-account.json"
    if fallback.is_file():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(fallback)
        logger.info("Auto-discovered credentials at %s", fallback)
        return str(fallback)

    return None


def can_run_real_pipeline() -> bool:
    """Check whether Vision credentials are available."""
    cred = _ensure_credentials()
    logger.info("can_run_real_pipeline: credentials=%s", cred)
    return cred is not None


def run_real_extraction(job_public_id: str) -> None:
    """Run the full deterministic extraction pipeline.

    PDF → page images → Vision OCR per page → detect anchors →
    build bboxes → crop → OCR synthesis from page tokens →
    fallback per-crop OCR only for low-confidence questions → finalise.

    Progress stages:
        preprocess       →  0–20 %
        layout_analysis  → 20–40 %
        crop_questions   → 40–60 %
        ocr              → 60–80 %
        done             → 100 %
    """
    db: Session = _get_session_factory()()
    try:
        result = _load_job_and_set(db, job_public_id)
        if result is None:
            logger.error("Job %s not found", job_public_id)
            return

        job, set_obj = result
        job.status = "running"
        db.commit()

        # Heavy / optional imports deferred to avoid startup failures.
        # Keep these inside try so dependency/import errors are captured
        # and job status is moved to failed instead of staying queued.
        from app.ocr.vision_client import VisionOCRClient
        from app.pipeline.crop import crop_questions_from_page, save_question_image
        from app.pipeline.debug import draw_bboxes
        from app.pipeline.ingest import render_pdf_to_images
        from app.pipeline.layout import build_question_bboxes, detect_question_anchors_with_page
        from app.pipeline.ocr_step import _flatten_tokens, run_ocr_for_question
        from app.pipeline.structure_step import run_gemini_structuring

        # ── 1. Load source file  (preprocess 0–10 %) ─────────────────
        _update_job(db, job, "preprocess", 0.05)

        file_key = set_obj.file_key
        if not file_key:
            raise RuntimeError("Set has no file_key — file was not persisted")

        source_path = _UPLOADS_DIR / file_key
        if not source_path.exists():
            raise FileNotFoundError(f"Source file missing: {source_path}")

        pdf_bytes = source_path.read_bytes()
        mime = set_obj.source_mime or ""

        # ── 2. Render pages  (preprocess 10–20 %) ────────────────────
        _update_job(db, job, "preprocess", 0.10)

        if "pdf" in mime.lower():
            page_images = render_pdf_to_images(pdf_bytes)
        else:
            from PIL import Image
            page_images = [Image.open(io.BytesIO(pdf_bytes)).convert("RGB")]

        logger.info("Rendered %d page(s) for set %s", len(page_images), set_obj.public_id)
        _update_job(db, job, "preprocess", 0.20)

        # ── 3. Per-page: page-OCR → anchors → bboxes → crops (20–60 %)
        vision_client = VisionOCRClient()
        total_questions = 0
        order_index = 0
        crops_dir = _UPLOADS_DIR / set_obj.public_id / "crops"
        all_question_rows: list[Question] = []
        n_pages = max(len(page_images), 1)

        for page_no, page_img in enumerate(page_images):
            page_w, page_h = page_img.size

            # OCR the full page for layout analysis.
            buf = io.BytesIO()
            page_img.save(buf, format="PNG")
            page_bytes = buf.getvalue()

            ocr_result = vision_client.ocr_document_bytes(page_bytes)
            flat_tokens = _flatten_tokens(ocr_result["pages"])

            progress_la = 0.20 + 0.20 * ((page_no + 0.5) / n_pages)
            _update_job(db, job, "layout_analysis", round(progress_la, 2))

            # Detect question anchors.
            anchors = detect_question_anchors_with_page(flat_tokens, page_height=page_h)
            bboxes = build_question_bboxes(anchors, page_w, page_h)

            logger.info(
                "Page %d: %d tokens, %d anchors, %d bboxes",
                page_no, len(flat_tokens), len(anchors), len(bboxes),
            )

            # Debug: save annotated page.
            if bboxes:
                debug_path = _DEBUG_DIR / set_obj.public_id / f"page_{page_no}_bboxes.png"
                draw_bboxes(page_img, bboxes, debug_path)

            progress_crop = 0.40 + 0.20 * ((page_no + 1) / n_pages)
            _update_job(db, job, "crop_questions", round(progress_crop, 2))

            # Crop and persist.
            crops = crop_questions_from_page(page_img, bboxes)

            for bbox, crop_img in zip(bboxes, crops):
                order_index += 1
                q_public_id = new_public_id("q_")

                crop_filename = f"{q_public_id}.png"
                crop_path = crops_dir / crop_filename
                save_question_image(crop_img, crop_path)

                image_key = f"{set_obj.public_id}/crops/{crop_filename}"

                q = Question(
                    public_id=q_public_id,
                    set_id=set_obj.id,
                    order_index=order_index,
                    number_label=bbox["number_label"],
                    cropped_image_key=image_key,
                    metadata_json=_build_question_context_metadata(
                        source_page=page_no,
                        bbox=bbox,
                    ),
                    review_status="unreviewed",
                )
                _apply_page_ocr_to_question(q, flat_tokens, bbox)
                db.add(q)
                all_question_rows.append(q)

            total_questions += len(crops)

        db.flush()

        # ── 4. Fallback OCR on low-confidence crops only (60–80 %) ───
        _update_job(db, job, "ocr", 0.60)
        fallback_rows = [
            q for q in all_question_rows
            if q.review_status == "auto_flagged" or not (q.ocr_text or "").strip()
        ]
        logger.info(
            "Fallback OCR targets: %d/%d question(s)",
            len(fallback_rows),
            len(all_question_rows),
        )

        if fallback_rows:
            progress_step = max(1, len(fallback_rows) // 5)
            for i, q in enumerate(fallback_rows):
                crop_path = _UPLOADS_DIR / q.cropped_image_key
                try:
                    if not crop_path.exists():
                        raise FileNotFoundError(f"Crop file missing: {crop_path}")
                    run_ocr_for_question(
                        db,
                        q,
                        crop_path.read_bytes(),
                        client=vision_client,
                        commit=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Fallback OCR failed for question %s: %s",
                        q.public_id,
                        _format_exception(exc, limit=_MAX_QUESTION_ERROR_LEN),
                    )
                    _mark_question_step_error(q, "ocr", exc)
                    db.add(q)

                if (i + 1) % progress_step == 0 or (i + 1) == len(fallback_rows):
                    progress_ocr = 0.60 + 0.20 * ((i + 1) / len(fallback_rows))
                    _update_job(db, job, "ocr", round(progress_ocr, 2))

            db.commit()
        else:
            _update_job(db, job, "ocr", 0.80)

        # ── 5. Gemini structuring (→ 90 %) ───────────────────────────
        _update_job(db, job, "structuring", 0.90)
        for q in all_question_rows:
            run_gemini_structuring(db, q)

        # ── 6. Finalise (→ 100 %) ────────────────────────────────────
        flagged_count = sum(1 for q in all_question_rows if q.review_status == "auto_flagged")
        empty_ocr_count = sum(1 for q in all_question_rows if not (q.ocr_text or "").strip())
        fallback_count = len(fallback_rows)
        has_flagged = flagged_count > 0
        set_obj.status = "needs_review" if has_flagged else "ready"
        set_obj.question_count = total_questions
        denom = max(total_questions, 1)
        quality_metrics = {
            "flagged_count": flagged_count,
            "flagged_ratio": round(flagged_count / denom, 4),
            "empty_ocr_count": empty_ocr_count,
            "empty_ocr_ratio": round(empty_ocr_count / denom, 4),
            "fallback_ocr_count": fallback_count,
            "fallback_ocr_ratio": round(fallback_count / denom, 4),
        }
        options = dict(job.options or {})
        options["quality_metrics"] = quality_metrics
        job.options = options
        job.status = "done"
        job.stage = "done"
        job.progress = 1.0
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Extraction complete for job %s: %d questions (status=%s)",
            job_public_id, total_questions, set_obj.status,
        )
        logger.info("Quality metrics for job %s: %s", job_public_id, quality_metrics)

    except Exception as exc:
        logger.exception("Extraction failed for job %s", job_public_id)
        try:
            db.rollback()
            result = _load_job_and_set(db, job_public_id)
            if result is not None:
                job, set_obj = result
                job.status = "failed"
                job.error_message = _format_exception(exc, limit=_MAX_JOB_ERROR_LEN)
                set_obj.status = "error"
                # Preserve partial progress visibility if questions were already inserted.
                q_count_stmt = (
                    select(func.count())
                    .select_from(Question)
                    .where(Question.set_id == set_obj.id)
                )
                set_obj.question_count = int(db.execute(q_count_stmt).scalar_one() or 0)
                db.commit()
        except Exception:
            logger.exception("Failed to mark job as failed")
    finally:
        db.close()
