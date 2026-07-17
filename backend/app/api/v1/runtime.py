from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import List
from app.db.database import get_db
from app.services.runtime_service import runtime_service
from app.services.session_service import session_service
from app.services.meeting_runtime_service import meeting_runtime_service
from app.services.qa_service import qa_service
from app.models.runtime_message import RuntimeMessage
from app.models.organization_config import OrganizationConfig

router = APIRouter(prefix="/runtime", tags=["Orchestration Runtime"])

class AskQuestionRequest(BaseModel):
    speaker_name: str
    question_text: str

class MessageResponse(BaseModel):
    id: str
    session_id: str
    speaker_name: str
    message_text: str
    timestamp: str

    class Config:
        orm_mode = True

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
    Sprint 3 & 4: Returns running meeting status combined with readiness and QA counters.
    """
    try:
        readiness = session_service.validate_readiness(db, session_id)
        db_runtime = meeting_runtime_service.get_runtime(db, session_id)
        
        # Fetch question speaker count
        config = db.query(OrganizationConfig).first()
        trainer = config.ai_trainer_name if config else "KONE Trainer"
        questions = db.query(RuntimeMessage).filter(
            RuntimeMessage.session_id == session_id,
            RuntimeMessage.speaker_name != trainer
        ).all()

        return {
            "session_id": session_id,
            "state": db_runtime.state,
            "current_slide": db_runtime.current_slide,
            "last_heartbeat": db_runtime.last_heartbeat.isoformat() if db_runtime.last_heartbeat else None,
            "questions_asked": len(questions),
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

@router.post("/{session_id}/ask")
async def ask_attendee_question(session_id: str, req: AskQuestionRequest, db: DBSession = Depends(get_db)):
    try:
        res = await qa_service.ask_question(
            db=db,
            session_id=session_id,
            speaker_name=req.speaker_name,
            question_text=req.question_text
        )
        return res
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{session_id}/conversation")
def get_conversation_history(session_id: str, db: DBSession = Depends(get_db)):
    history = qa_service.get_conversation_history(db, session_id)
    return [
        {
            "id": msg.id,
            "session_id": msg.session_id,
            "speaker_name": msg.speaker_name,
            "message_text": msg.message_text,
            "timestamp": msg.timestamp.isoformat()
        }
        for msg in history
    ]
