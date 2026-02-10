"""Routes for /v1/questions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repo.questions import get_question_by_public_id, patch_question_by_public_id
from app.schemas.question import OkResponse, QuestionDetailResponse, QuestionPatchRequest

router = APIRouter(prefix="/v1/questions", tags=["questions"])


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
