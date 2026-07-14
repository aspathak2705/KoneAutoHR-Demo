from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db
from app.schemas.presentation_question import PresentationQuestionResponse, PresentationQuestionUpdate
from app.services.presentation_question_service import presentation_question_service
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/presentation-questions", tags=["Saved Employee Questions"])

class QuestionsRegenerateRequest(BaseModel):
    presentation_id: str
    employee_list_id: str
    company_name: Optional[str] = "KONE"

@router.get("/{presentation_id}", response_model=PresentationQuestionResponse)
def get_presentation_questions(presentation_id: str, db: DBSession = Depends(get_db)):
    questions = presentation_question_service.get_active_questions(db, presentation_id)
    if not questions:
        raise HTTPException(status_code=404, detail="No active questions found for this presentation")
    return questions

@router.put("/{id}", response_model=PresentationQuestionResponse)
def update_presentation_questions(
    id: str,
    payload: PresentationQuestionUpdate,
    db: DBSession = Depends(get_db)
):
    try:
        return presentation_question_service.update_questions(db, id, payload.questions_content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/regenerate", response_model=PresentationQuestionResponse, status_code=status.HTTP_201_CREATED)
async def regenerate_presentation_questions(
    payload: QuestionsRegenerateRequest,
    db: DBSession = Depends(get_db)
):
    try:
        return await presentation_question_service.generate_questions_only(
            db, 
            payload.presentation_id, 
            payload.employee_list_id, 
            payload.company_name
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
