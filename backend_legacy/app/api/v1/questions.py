"""Routes for /v1/questions."""

import logging
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.question import Question
from app.pipeline.reprocess_step import reprocess_question
from app.repo.questions import get_question_by_public_id, patch_question_by_public_id
from app.repo.question_variants import create_question_variant, list_question_variants
from app.schemas.question import (
    HintRequest,
    HintResponse,
    OkResponse,
    QuestionDetailResponse,
    QuestionPatchRequest,
    ReprocessResponse,
    VariantCreateRequest,
    VariantListResponse,
    VariantResponse,
)
from app.services.hint_generator import generate_hint
from app.services.variant_generator import generate_variant

router = APIRouter(prefix="/v1/questions", tags=["questions"])
logger = logging.getLogger(__name__)
_STRICT_REVIEW_STATUSES = {"approved", "rejected"}
_HINT_RATE_WINDOW_SECONDS = 60
_HINT_RATE_LIMIT = 12
_HINT_RATE_BUCKET: dict[str, list[float]] = {}


def _to_uploads_url(file_key: str | None) -> str | None:
    if not file_key:
        return None
    return f"/uploads/{quote(file_key, safe='/')}"


def _sync_set_status(db: Session, question) -> None:
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


def _check_hint_rate_limit(question_public_id: str) -> None:
    now = time.time()
    bucket = _HINT_RATE_BUCKET.get(question_public_id, [])
    bucket = [ts for ts in bucket if now - ts <= _HINT_RATE_WINDOW_SECONDS]
    if len(bucket) >= _HINT_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many hint requests. Please retry shortly.")
    bucket.append(now)
    _HINT_RATE_BUCKET[question_public_id] = bucket


def _variant_row_to_response(row) -> VariantResponse:
    return VariantResponse(
        variantId=str(row.id),
        variantType=row.variant_type,
        body=row.body,
        answer=row.answer,
        explanation=row.explanation,
        model=row.model,
        createdAt=row.created_at.isoformat() if row.created_at else "",
    )


@router.get("/{question_public_id}", response_model=QuestionDetailResponse)
async def get_question(question_public_id: str, db: Session = Depends(get_db)):
    """Get question detail from DB."""
    question = get_question_by_public_id(db, question_public_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return QuestionDetailResponse(
        questionId=question.public_id,
        setId=question.set.public_id,
        numberLabel=question.number_label,
        orderIndex=question.order_index,
        croppedImageUrl=_to_uploads_url(question.cropped_image_key),
        ocrText=question.ocr_text,
        structure=question.structure,
        metadata=question.metadata_json,
        confidence=question.confidence,
        reviewStatus=question.review_status,
    )


@router.patch("/{question_public_id}", response_model=OkResponse)
async def patch_question(
    question_public_id: str,
    body: QuestionPatchRequest,
    db: Session = Depends(get_db),
):
    """Patch question fields in DB."""
    question = patch_question_by_public_id(
        db,
        public_id=question_public_id,
        ocr_text=body.ocrText,
        structure=body.structure,
        metadata=body.metadata,
        review_status=body.reviewStatus,
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return OkResponse()


@router.post("/{question_public_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_question_route(question_public_id: str, db: Session = Depends(get_db)):
    question = get_question_by_public_id(db, question_public_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        reprocess_question(db, question)
        db.refresh(question)
    except Exception as exc:  # noqa: BLE001
        metadata = dict(question.metadata_json or {})
        metadata["reprocess_error"] = {"type": type(exc).__name__, "message": str(exc)[:400]}
        question.metadata_json = metadata
        if question.review_status not in _STRICT_REVIEW_STATUSES:
            question.review_status = "auto_flagged"
        db.add(question)
        db.commit()
        db.refresh(question)
        _sync_set_status(db, question)
        raise HTTPException(status_code=500, detail="Question reprocess failed") from exc

    return ReprocessResponse(
        questionId=question.public_id,
        setId=question.set.public_id,
        reviewStatus=question.review_status,
    )


@router.post("/{question_public_id}/variants", response_model=VariantResponse)
async def create_variant_route(
    question_public_id: str,
    body: VariantCreateRequest,
    db: Session = Depends(get_db),
):
    started_at = time.perf_counter()
    question = get_question_by_public_id(db, question_public_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    parsed = (question.structure or {}).get("parsed_v1")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Question has no parsed_v1 structure yet")

    payload, model_name = generate_variant(parsed, variant_type=body.variantType)
    row = create_question_variant(
        db,
        question=question,
        variant_type=payload["variant_type"],
        body=payload["body"],
        answer=payload.get("answer"),
        explanation=payload.get("explanation"),
        model=model_name,
    )
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "variant_generated question=%s model=%s duration_ms=%d",
        question.public_id,
        model_name,
        duration_ms,
    )
    return _variant_row_to_response(row)


@router.get("/{question_public_id}/variants", response_model=VariantListResponse)
async def list_variant_route(question_public_id: str, db: Session = Depends(get_db)):
    question = get_question_by_public_id(db, question_public_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    rows = list_question_variants(db, question=question)
    return VariantListResponse(
        questionId=question.public_id,
        variants=[_variant_row_to_response(row) for row in rows],
    )


@router.post("/{question_public_id}/hint", response_model=HintResponse)
async def create_hint_route(
    question_public_id: str,
    body: HintRequest,
    db: Session = Depends(get_db),
):
    started_at = time.perf_counter()
    _check_hint_rate_limit(question_public_id)
    question = get_question_by_public_id(db, question_public_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    parsed = (question.structure or {}).get("parsed_v1")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Question has no parsed_v1 structure yet")

    recent_chat = [{"role": item.role, "text": item.text} for item in body.recentChat]
    payload, model_name = generate_hint(
        parsed=parsed,
        recent_chat=recent_chat,
        level=body.level,
        stroke_summary=body.strokeSummary,
    )
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "hint_generated question=%s level=%s model=%s duration_ms=%d",
        question.public_id,
        payload["level"],
        model_name,
        duration_ms,
    )
    return HintResponse(
        questionId=question.public_id,
        level=payload["level"],
        hint=payload["hint"],
        model=model_name,
    )
