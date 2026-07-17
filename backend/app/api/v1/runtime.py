from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db
from app.services.runtime_service import runtime_service
from app.services.session_service import session_service
from app.services.meeting_runtime_service import meeting_runtime_service

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
def get_runtime_status(session_id: str, db: DBSession = Depends(get_db)):
    """
    Sprint 3: Returns running meeting status combined with readiness.
    """
    try:
        readiness = session_service.validate_readiness(db, session_id)
        db_runtime = meeting_runtime_service.get_runtime(db, session_id)
        return {
            "session_id": session_id,
            "state": db_runtime.state,
            "current_slide": db_runtime.current_slide,
            "last_heartbeat": db_runtime.last_heartbeat.isoformat() if db_runtime.last_heartbeat else None,
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

@router.post("/{session_id}/start")
def start_runtime(session_id: str, db: DBSession = Depends(get_db)):
    meeting_runtime_service.start_meeting(session_id)
    return {"message": "AI meeting orchestration session launched."}

@router.post("/{session_id}/stop")
def stop_runtime(session_id: str, db: DBSession = Depends(get_db)):
    meeting_runtime_service.stop_meeting(session_id)
    return {"message": "AI meeting orchestration session stopped."}

@router.post("/{session_id}/next")
async def advance_runtime_slide(session_id: str, db: DBSession = Depends(get_db)):
    new_slide = await meeting_runtime_service.advance_slide(session_id)
    return {"current_slide": new_slide}

@router.post("/{session_id}/prev")
async def previous_runtime_slide(session_id: str, db: DBSession = Depends(get_db)):
    new_slide = await meeting_runtime_service.previous_slide(session_id)
    return {"current_slide": new_slide}
