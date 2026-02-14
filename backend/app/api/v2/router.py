from __future__ import annotations

import os
import threading

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.v2.dependencies import (
    provide_document_processing_service,
    provide_document_service,
    provide_generation_service,
    provide_review_service,
    provide_store,
)
from app.api.v2.schemas.document import DocumentCreateResponse
from app.api.v2.schemas.job import JobDetailResponse, JobEventItem, JobEventListResponse
from app.api.v2.schemas.question import QuestionDetailResponse, QuestionReprocessResponse
from app.api.v2.schemas.review import ReviewPatchRequest, ReviewPatchResponse, ReviewQueueItem, ReviewQueueResponse
from app.api.v2.schemas.set import (
    SetDeleteResponse,
    SetDetailResponse,
    SetListResponse,
    SetQuestionListResponse,
    SetQuestionSummary,
    SetSummaryResponse,
)
from app.api.v2.schemas.tutor import HintRequest, HintResponse
from app.api.v2.schemas.variant import VariantCreateRequest, VariantCreateResponse, VariantItem, VariantListResponse
from app.application.generation import AIGenerationService
from app.application.services import DocumentApplicationService, DocumentProcessingService, ReviewApplicationService
from app.infra.db.store import DatabaseStore

router = APIRouter(prefix="/v2", tags=["v2"])


def _cropped_image_url(metadata: dict | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("croppedImageUrl")
    if isinstance(value, str) and value.strip():
        return value
    return None


@router.post("/documents", response_model=DocumentCreateResponse)
async def create_document(
    file: UploadFile = File(...),
    service: DocumentApplicationService = Depends(provide_document_service),
    processing_service: DocumentProcessingService = Depends(provide_document_processing_service),
):
    payload = await file.read()
    try:
        data = service.create_document(
            filename=file.filename,
            content_type=file.content_type,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    kwargs = {
        "job_id": data["jobId"],
        "set_id": data["setId"],
        "filename": file.filename,
        "content_type": file.content_type,
        "payload": payload,
    }
    if os.getenv("SEDU_SYNC_PROCESSING") == "1":
        processing_service.process_document(**kwargs)
    else:
        threading.Thread(
            target=processing_service.process_document,
            kwargs=kwargs,
            daemon=True,
        ).start()

    return DocumentCreateResponse(**data)


@router.get("/jobs/{jobId}", response_model=JobDetailResponse)
async def get_job(jobId: str, store: DatabaseStore = Depends(provide_store)):
    row = store.get_job(jobId)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobDetailResponse(
        jobId=row.job_id,
        setId=row.set_id,
        status=row.status,
        stage=row.stage,
        percent=row.percent,
        errorMessage=row.error_message,
    )


@router.get("/jobs/{jobId}/events", response_model=JobEventListResponse)
async def get_job_events(jobId: str, store: DatabaseStore = Depends(provide_store)):
    if store.get_job(jobId) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    items = [
        JobEventItem(
            status=item.status,
            stage=item.stage,
            percent=item.percent,
            createdAt=item.created_at,
        )
        for item in store.list_job_events(jobId)
    ]
    return JobEventListResponse(jobId=jobId, events=items)


@router.get("/sets", response_model=SetListResponse)
async def list_sets(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    store: DatabaseStore = Depends(provide_store),
):
    rows = store.list_sets(limit=limit, offset=offset, status=status)
    return SetListResponse(
        sets=[
            SetSummaryResponse(
                setId=row.set_id,
                status=row.status,
                title=row.title,
                questionCount=row.question_count,
                sourceFilename=row.source_filename,
            )
            for row in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/sets/{setId}", response_model=SetDetailResponse)
async def get_set(setId: str, store: DatabaseStore = Depends(provide_store)):
    row = store.get_set(setId)
    if row is None:
        raise HTTPException(status_code=404, detail="Set not found")

    return SetDetailResponse(
        setId=row.set_id,
        status=row.status,
        latestJobId=store.get_latest_job_id_for_set(setId),
        title=row.title,
        sourceFilename=row.source_filename,
        sourceMime=row.source_mime,
        sourceSize=row.source_size,
        questionCount=row.question_count,
    )


@router.delete("/sets/{setId}", response_model=SetDeleteResponse)
async def delete_set(setId: str, store: DatabaseStore = Depends(provide_store)):
    deleted = store.delete_set(setId)
    if not deleted:
        raise HTTPException(status_code=404, detail="Set not found")

    return SetDeleteResponse(setId=setId)


@router.get("/sets/{setId}/questions", response_model=SetQuestionListResponse)
async def list_set_questions(setId: str, store: DatabaseStore = Depends(provide_store)):
    if store.get_set(setId) is None:
        raise HTTPException(status_code=404, detail="Set not found")

    items = [
        SetQuestionSummary(
            questionId=q.question_id,
            numberLabel=q.number_label,
            orderIndex=q.order_index,
            reviewStatus=q.review_status,
            confidence=q.confidence,
            croppedImageUrl=_cropped_image_url(q.metadata),
        )
        for q in store.list_questions_for_set(setId)
    ]
    return SetQuestionListResponse(setId=setId, questions=items)


@router.get("/questions/{questionId}", response_model=QuestionDetailResponse)
async def get_question(questionId: str, store: DatabaseStore = Depends(provide_store)):
    row = store.get_question(questionId)
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return QuestionDetailResponse(
        questionId=row.question_id,
        setId=row.set_id,
        numberLabel=row.number_label,
        orderIndex=row.order_index,
        reviewStatus=row.review_status,
        confidence=row.confidence,
        croppedImageUrl=_cropped_image_url(row.metadata),
        ocrText=row.ocr_text,
        metadata=row.metadata,
        structure=row.structure,
    )


@router.post("/questions/{questionId}/reprocess", response_model=QuestionReprocessResponse)
async def reprocess_question(questionId: str, store: DatabaseStore = Depends(provide_store)):
    row = store.reprocess_question(questionId)
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return QuestionReprocessResponse(
        questionId=row.question_id,
        setId=row.set_id,
        reviewStatus=row.review_status,
    )


@router.get("/questions/{questionId}/variants", response_model=VariantListResponse)
async def list_question_variants(questionId: str, store: DatabaseStore = Depends(provide_store)):
    if store.get_question(questionId) is None:
        raise HTTPException(status_code=404, detail="Question not found")

    rows = store.list_variants_for_question(questionId)
    return VariantListResponse(
        questionId=questionId,
        variants=[
            VariantItem(
                variantId=row.variant_id,
                questionId=row.question_id,
                variantType=row.variant_type,  # type: ignore[arg-type]
                body=row.body,
                answer=row.answer,
                explanation=row.explanation,
                model=row.model,
                createdAt=row.created_at,
            )
            for row in rows
        ],
    )


@router.post("/questions/{questionId}/variants", response_model=VariantCreateResponse)
async def create_question_variant(
    questionId: str,
    body: VariantCreateRequest,
    store: DatabaseStore = Depends(provide_store),
    service: AIGenerationService = Depends(provide_generation_service),
):
    question = store.get_question(questionId)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    generated = service.create_variant(
        question=question,
        variant_type=body.variantType,
    )
    if generated is None:
        raise HTTPException(status_code=500, detail="Variant generation failed")

    variant = VariantItem(
        variantId=generated.variant_id,
        questionId=generated.question_id,
        variantType=generated.variant_type,  # type: ignore[arg-type]
        body=generated.body,
        answer=generated.answer,
        explanation=generated.explanation,
        model=generated.model,
        createdAt=generated.created_at,
    )
    return VariantCreateResponse(questionId=questionId, variant=variant)


@router.post("/questions/{questionId}/hint", response_model=HintResponse)
async def create_question_hint(
    questionId: str,
    body: HintRequest,
    store: DatabaseStore = Depends(provide_store),
    service: AIGenerationService = Depends(provide_generation_service),
):
    question = store.get_question(questionId)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    hint = service.create_hint(
        question=question,
        level=body.level,
        recent_chat=[{"role": item.role, "text": item.text} for item in body.recentChat],
        stroke_summary=body.strokeSummary,
    )
    return HintResponse(
        questionId=questionId,
        level=hint.level,  # type: ignore[arg-type]
        hint=hint.hint,
        model=hint.model,
    )


@router.get("/review/queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    reviewStatus: str = Query(default="auto_flagged"),
    store: DatabaseStore = Depends(provide_store),
):
    items = [
        ReviewQueueItem(
            questionId=q.question_id,
            setId=q.set_id,
            numberLabel=q.number_label,
            orderIndex=q.order_index,
            reviewStatus=q.review_status,
            confidence=q.confidence,
            metadata=q.metadata,
        )
        for q in store.list_review_queue(review_status=reviewStatus)
    ]
    return ReviewQueueResponse(items=items, count=len(items))


@router.patch("/questions/{questionId}/review", response_model=ReviewPatchResponse)
async def patch_question_review(
    questionId: str,
    body: ReviewPatchRequest,
    service: ReviewApplicationService = Depends(provide_review_service),
):
    row = service.apply_review(
        question_id=questionId,
        reviewer=body.reviewer,
        review_status=body.reviewStatus,
        note=body.note,
        metadata_patch=body.metadataPatch,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return ReviewPatchResponse(
        questionId=row.question_id,
        reviewStatus=row.review_status,
        metadata=row.metadata,
    )
