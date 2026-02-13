from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile

from app.api.v2.dependencies import get_document_processing_service, get_document_service, get_review_service, get_store
from app.api.v2.schemas.document import DocumentCreateResponse
from app.api.v2.schemas.job import JobDetailResponse, JobEventItem, JobEventListResponse
from app.api.v2.schemas.question import QuestionDetailResponse, QuestionReprocessResponse
from app.api.v2.schemas.review import ReviewPatchRequest, ReviewPatchResponse, ReviewQueueItem, ReviewQueueResponse
from app.api.v2.schemas.set import (
    SetDetailResponse,
    SetListResponse,
    SetQuestionListResponse,
    SetQuestionSummary,
    SetSummaryResponse,
)
from app.application.services import DocumentApplicationService, DocumentProcessingService, ReviewApplicationService
from app.infra.db.store import DatabaseStore

router = APIRouter(prefix="/v2", tags=["v2"])


@router.post("/documents", response_model=DocumentCreateResponse)
async def create_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service: DocumentApplicationService = Depends(get_document_service),
    processing_service: DocumentProcessingService = Depends(get_document_processing_service),
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

    background_tasks.add_task(
        processing_service.process_document,
        job_id=data["jobId"],
        filename=file.filename,
        content_type=file.content_type,
        payload=payload,
    )

    return DocumentCreateResponse(**data)


@router.get("/jobs/{jobId}", response_model=JobDetailResponse)
def get_job(jobId: str, store: DatabaseStore = Depends(get_store)):
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
def get_job_events(jobId: str, store: DatabaseStore = Depends(get_store)):
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
def list_sets(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    store: DatabaseStore = Depends(get_store),
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
def get_set(setId: str, store: DatabaseStore = Depends(get_store)):
    row = store.get_set(setId)
    if row is None:
        raise HTTPException(status_code=404, detail="Set not found")

    return SetDetailResponse(
        setId=row.set_id,
        status=row.status,
        title=row.title,
        sourceFilename=row.source_filename,
        sourceMime=row.source_mime,
        sourceSize=row.source_size,
        questionCount=row.question_count,
    )


@router.get("/sets/{setId}/questions", response_model=SetQuestionListResponse)
def list_set_questions(setId: str, store: DatabaseStore = Depends(get_store)):
    if store.get_set(setId) is None:
        raise HTTPException(status_code=404, detail="Set not found")

    items = [
        SetQuestionSummary(
            questionId=q.question_id,
            numberLabel=q.number_label,
            orderIndex=q.order_index,
            reviewStatus=q.review_status,
            confidence=q.confidence,
        )
        for q in store.list_questions_for_set(setId)
    ]
    return SetQuestionListResponse(setId=setId, questions=items)


@router.get("/questions/{questionId}", response_model=QuestionDetailResponse)
def get_question(questionId: str, store: DatabaseStore = Depends(get_store)):
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
        ocrText=row.ocr_text,
        metadata=row.metadata,
        structure=row.structure,
    )


@router.post("/questions/{questionId}/reprocess", response_model=QuestionReprocessResponse)
def reprocess_question(questionId: str, store: DatabaseStore = Depends(get_store)):
    row = store.reprocess_question(questionId)
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return QuestionReprocessResponse(
        questionId=row.question_id,
        setId=row.set_id,
        reviewStatus=row.review_status,
    )


@router.get("/review/queue", response_model=ReviewQueueResponse)
def get_review_queue(
    reviewStatus: str = Query(default="auto_flagged"),
    store: DatabaseStore = Depends(get_store),
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
def patch_question_review(
    questionId: str,
    body: ReviewPatchRequest,
    service: ReviewApplicationService = Depends(get_review_service),
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
