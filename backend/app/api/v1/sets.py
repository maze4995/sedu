"""Routes for /v1/sets."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repo.jobs import create_job
from app.repo.questions import list_questions_for_set
from app.repo.sets import create_set, get_set_by_public_id
from app.schemas.question import QuestionListResponse, QuestionSummary
from app.schemas.set import SetCreatedResponse, SetDetailResponse
from app.services.extraction_simulator import run_fake_extraction

router = APIRouter(prefix="/v1/sets", tags=["sets"])


@router.post("", response_model=SetCreatedResponse)
async def create_set_route(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Upload a file, create a set, and auto-start extraction."""
    payload = await file.read()
    set_obj = create_set(
        db,
        source_filename=file.filename,
        source_mime=file.content_type,
        source_size=len(payload),
    )

    # Auto-create extraction job and start simulator.
    job = create_job(db, set_obj=set_obj)
    background_tasks.add_task(run_fake_extraction, job.public_id)

    return SetCreatedResponse(setId=set_obj.public_id, status=set_obj.status)


@router.get("/{set_public_id}", response_model=SetDetailResponse)
async def get_set(set_public_id: str, db: Session = Depends(get_db)):
    """Get set detail from DB."""
    set_obj = get_set_by_public_id(db, set_public_id)
    if set_obj is None:
        raise HTTPException(status_code=404, detail="Set not found")

    return SetDetailResponse(
        setId=set_obj.public_id,
        status=set_obj.status,
        title=set_obj.title,
        sourceFilename=set_obj.source_filename or set_obj.file_name,
        sourceMime=set_obj.source_mime,
        sourceSize=set_obj.source_size,
        questionCount=set_obj.question_count,
    )


@router.get("/{set_public_id}/questions", response_model=QuestionListResponse)
async def list_questions(set_public_id: str, db: Session = Depends(get_db)):
    """List questions in a set from DB."""
    set_obj = get_set_by_public_id(db, set_public_id)
    if set_obj is None:
        raise HTTPException(status_code=404, detail="Set not found")

    questions = list_questions_for_set(db, set_obj)
    question_rows = [
        QuestionSummary(
            questionId=question.public_id,
            numberLabel=question.number_label,
            orderIndex=question.order_index,
            reviewStatus=question.review_status,
        )
        for question in questions
    ]

    return QuestionListResponse(setId=set_obj.public_id, questions=question_rows)
