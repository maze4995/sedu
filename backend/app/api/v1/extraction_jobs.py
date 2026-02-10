"""Routes for extraction jobs."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repo.jobs import create_job, get_job_by_public_id
from app.repo.sets import get_set_by_public_id
from app.schemas.job import ExtractionJobCreatedResponse, ExtractionJobDetailResponse
from app.services.extraction_simulator import run_fake_extraction

router = APIRouter(tags=["extraction-jobs"])


@router.post("/v1/sets/{set_public_id}/extraction-jobs",
             response_model=ExtractionJobCreatedResponse)
async def create_extraction_job(
    set_public_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create an extraction job row and start the fake extraction simulator."""
    set_obj = get_set_by_public_id(db, set_public_id)
    if set_obj is None:
        raise HTTPException(status_code=404, detail="Set not found")

    job = create_job(db, set_obj=set_obj)

    background_tasks.add_task(run_fake_extraction, job.public_id)

    return ExtractionJobCreatedResponse(
        jobId=job.public_id,
        setId=set_obj.public_id,
        status=job.status,
    )


@router.get("/v1/extraction-jobs/{job_public_id}",
            response_model=ExtractionJobDetailResponse)
async def get_extraction_job(job_public_id: str, db: Session = Depends(get_db)):
    """Get extraction job status from DB."""
    job = get_job_by_public_id(db, job_public_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Extraction job not found")

    return ExtractionJobDetailResponse(
        jobId=job.public_id,
        setId=job.set.public_id,
        status=job.status,
        stage=job.stage,
        percent=job.progress * 100.0,
        errorMessage=job.error_message,
    )
