import os
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.services.storage_service import storage_service
from app.core.constants import UploadType
from app.core.exceptions import SessionNotFoundException
from app.modules.induction.services.induction_service import induction_service

router = APIRouter(prefix="/induction", tags=["Induction Preparation"])

@router.post("/{session_id}/prepare", status_code=status.HTTP_202_ACCEPTED)
def prepare_induction(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db)
):
    return induction_service.prepare_induction(db, session_id, background_tasks)

@router.get("/{session_id}/status")
def get_preparation_status(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    return induction_service.get_job_status(db, session_id)

@router.get("/{session_id}/package")
def get_induction_package(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    try:
        session_dir = storage_service.get_session_dir(session_id)
    except SessionNotFoundException:
        raise HTTPException(status_code=404, detail="Session not found")

    package_path = session_dir / "induction_package.json"
    if not package_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Induction Package has not been prepared yet. Trigger /prepare first."
        )
    return FileResponse(package_path, media_type="application/json", filename="induction_package.json")

@router.get("/{session_id}/preview")
def get_induction_preview(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    import json
    from app.repositories.session_repository import session_repository
    from app.repositories.presentation_script_repository import presentation_script_repository
    from app.repositories.presentation_question_repository import presentation_question_repository
    
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.presentation_id:
        script = presentation_script_repository.get_active(db, session.presentation_id)
        questions = presentation_question_repository.get_active(db, session.presentation_id)
        
        script_data = json.loads(script.script_content) if script else {}
        faq_data = json.loads(questions.questions_content) if questions else []
        
        return {
            "welcome_flow": script_data.get("welcome_flow"),
            "slide_narrations": script_data.get("slide_narrations"),
            "faq": faq_data,
            "closing_script": script_data.get("closing_script")
        }
        
    try:
        session_dir = storage_service.get_session_dir(session_id)
    except SessionNotFoundException:
        raise HTTPException(status_code=404, detail="Session not found")

    package_path = session_dir / "induction_package.json"
    if not package_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Induction Package has not been prepared yet. Trigger /prepare first."
        )
    try:
        with open(package_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read package: {str(e)}"
        )

    return {
        "welcome_flow": data.get("welcome_flow"),
        "slide_narrations": data.get("slide_narrations"),
        "faq": data.get("faq"),
        "closing_script": data.get("closing_script")
    }
