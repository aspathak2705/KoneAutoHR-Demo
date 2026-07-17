from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db
from app.services.runtime_service import runtime_service
from app.services.session_service import session_service

router = APIRouter(prefix="/runtime", tags=["Orchestration Runtime"])

@router.get("/{session_id}/context")
def get_runtime_context(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_service.get_runtime_context(db, session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{session_id}/voice-config")
def get_voice_config(session_id: str, db: DBSession = Depends(get_db)):
    return runtime_service.get_voice_config()

@router.get("/{session_id}/slide-controller")
def get_slide_controller(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_service.get_slide_controller(db, session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{session_id}")
def get_readiness_summary(session_id: str, db: DBSession = Depends(get_db)):
    """
    Sprint 2: Returns runtime readiness check values.
    """
    try:
        readiness = session_service.validate_readiness(db, session_id)
        return {
            "session_id": session_id,
            "presentation_ready": readiness.get("has_presentation") and readiness.get("has_script") and readiness.get("has_faq"),
            "employees_ready": readiness.get("has_employees"),
            "meeting_ready": readiness.get("has_meeting"),
            "ai_ready": readiness.get("has_script") and readiness.get("has_faq")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
