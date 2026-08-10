from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from sqlalchemy.orm import Session as DBSession
from typing import List
from app.db.database import get_db
from app.schemas.presentation import PresentationResponse
from app.services.presentation_service import presentation_service

router = APIRouter(prefix="/presentations", tags=["Saved Presentations"])

@router.get("", response_model=List[PresentationResponse])
def get_presentations(skip: int = 0, limit: int = 100, db: DBSession = Depends(get_db)):
    return presentation_service.get_all(db, skip, limit)

@router.post("", response_model=PresentationResponse, status_code=status.HTTP_201_CREATED)
async def upload_presentation(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db)
):
    try:
        return await presentation_service.create_presentation(db, name, file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{id}", response_model=PresentationResponse)
def get_presentation(id: str, db: DBSession = Depends(get_db)):
    pres = presentation_service.get(db, id)
    if not pres:
        raise HTTPException(status_code=404, detail="Presentation not found")
    return pres

@router.get("/{id}/assets-status")
def get_presentation_assets_status(id: str, mode: str = "AI", db: DBSession = Depends(get_db)):
    from app.modules.presentation.presentation_asset_manager import presentation_asset_manager
    try:
        return presentation_asset_manager.get_asset_status(db, id, mode)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{id}", response_model=PresentationResponse)
def delete_presentation(id: str, db: DBSession = Depends(get_db)):
    pres = presentation_service.delete(db, id)
    if not pres:
        raise HTTPException(status_code=404, detail="Presentation not found")
    return pres

from app.schemas.presentation_script import PresentationScriptResponse
from app.schemas.presentation_question import PresentationQuestionResponse

@router.get("/{id}/script", response_model=PresentationScriptResponse)
def get_presentation_script_nested(id: str, db: DBSession = Depends(get_db)):
    from app.services.presentation_script_service import presentation_script_service
    script = presentation_script_service.get_active_script(db, id)
    if not script:
        raise HTTPException(status_code=404, detail="No active script found for this presentation")
    return script

@router.get("/{id}/questions", response_model=PresentationQuestionResponse)
def get_presentation_questions_nested(id: str, db: DBSession = Depends(get_db)):
    from app.services.presentation_question_service import presentation_question_service
    questions = presentation_question_service.get_active_questions(db, id)
    if not questions:
        raise HTTPException(status_code=404, detail="No active questions found for this presentation")
    return questions
