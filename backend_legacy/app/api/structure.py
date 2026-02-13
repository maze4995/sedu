"""Routes for manual Gemini structuring actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.pipeline.structure_step import run_gemini_structuring
from app.repo.questions import get_question_by_public_id

router = APIRouter(tags=["structure"])


class StructureRunResponse(BaseModel):
    ok: bool = True
    questionId: str


@router.post("/v1/questions/{question_public_id}/structure", response_model=StructureRunResponse)
async def run_structure(question_public_id: str, db: Session = Depends(get_db)):
    question = get_question_by_public_id(db, question_public_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    run_gemini_structuring(db, question)
    return StructureRunResponse(questionId=question.public_id)


@router.get("/v1/questions/{question_public_id}/structure")
async def get_structure(question_public_id: str, db: Session = Depends(get_db)):
    question = get_question_by_public_id(db, question_public_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    structure = question.structure or {}
    return structure.get("parsed_v1")
