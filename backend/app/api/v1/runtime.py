from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import List
from app.db.database import get_db
from app.services.runtime_service import runtime_service
from app.services.session_service import session_service
from app.services.meeting_runtime_service import meeting_runtime_service
from app.services.teams_runtime_service import teams_runtime_service
from app.services.speech_runtime import speech_runtime_service
from app.services.qa_service import qa_service
from app.services.report_service import report_service
from app.models.runtime_message import RuntimeMessage
from app.models.organization_config import OrganizationConfig

from app.services.runtime_scheduler_service import runtime_scheduler_service
from app.services.runtime_validation_service import runtime_validation_service

router = APIRouter(prefix="/runtime", tags=["Orchestration Runtime"])

@router.post("/{session_id}/schedule")
def schedule_runtime_meeting(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_scheduler_service.schedule_session(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/schedule")
def get_runtime_schedule(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_scheduler_service.get_schedule_status(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/validate")
def validate_runtime(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_validation_service.validate_runtime_readiness(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/phase2b-handover")
def get_phase2b_handover_context(session_id: str, db: DBSession = Depends(get_db)):
    try:
        db_runtime = meeting_runtime_service.get_runtime(db, session_id)
        if db_runtime.state not in ["CONNECTED", "WAITING", "COMPLETED"]:
            raise HTTPException(
                status_code=400,
                detail=f"Runtime not ready for Phase 2B handover. Current state is {db_runtime.state}. Must be CONNECTED & WAITING."
            )
        return {
            "handover_status": "READY",
            "runtime_state": db_runtime.state,
            "context": runtime_service.get_runtime_context(db, session_id)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

class AskQuestionRequest(BaseModel):
    speaker_name: str
    question_text: str

class SpeakRequest(BaseModel):
    narration_text: str

class MessageResponse(BaseModel):
    id: str
    session_id: str
    speaker_name: str
    message_text: str
    timestamp: str

    class Config:
        from_attributes = True

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

from app.services.runtime_context_service import runtime_context_service
from app.services.runtime_readiness_service import runtime_readiness_service

@router.get("/readiness/{session_id}")
def get_unified_runtime_readiness(session_id: str, db: DBSession = Depends(get_db)):
    """
    Phase 4 — Unified Readiness API
    Returns authoritative, single-source-of-truth readiness report for a session with HTTP 200 OK.
    Never returns HTTP 400 for missing assets.
    """
    context = runtime_context_service.build_runtime_context(db, session_id)
    return runtime_readiness_service.evaluate_readiness(context)

@router.get("/{session_id}/status")
def get_runtime_status_detailed(session_id: str, db: DBSession = Depends(get_db)):
    """
    Sprint RC-1: Returns detailed connection state logs.
    """
    return teams_runtime_service.get_status(db, session_id)

@router.get("/{session_id}")
def get_runtime_status(session_id: str, db: DBSession = Depends(get_db)):
    """
    Sprint 3 & 4: Returns running meeting status combined with readiness and QA counters.
    Never fails with 400 if session assets are not fully ready.
    """
    context = runtime_context_service.build_runtime_context(db, session_id)
    readiness = runtime_readiness_service.evaluate_readiness(context)
    
    db_runtime = meeting_runtime_service.get_runtime(db, session_id)
    state = db_runtime.state if db_runtime else "IDLE"
    current_slide = db_runtime.current_slide if db_runtime else 0
    reconnect_count = db_runtime.reconnect_count if db_runtime else 0
    speech_state = db_runtime.speech_state if db_runtime else "IDLE"
    last_hb = db_runtime.last_heartbeat.isoformat() if db_runtime and db_runtime.last_heartbeat else None
    
    # Fetch question speaker count
    config = db.query(OrganizationConfig).first()
    trainer = config.ai_trainer_name if config else "KONE Trainer"
    questions = db.query(RuntimeMessage).filter(
        RuntimeMessage.session_id == session_id,
        RuntimeMessage.speaker_name != trainer
    ).all()

    return {
        "session_id": session_id,
        "state": state,
        "current_slide": current_slide,
        "reconnect_count": reconnect_count,
        "speech_state": speech_state,
        "last_heartbeat": last_hb,
        "questions_asked": len(questions),
        "presentation_ready": readiness.get("has_presentation") and readiness.get("has_script") and readiness.get("has_faq"),
        "employees_ready": readiness.get("has_employees"),
        "meeting_ready": readiness.get("has_meeting"),
        "ai_ready": readiness.get("has_script") and readiness.get("has_faq"),
        "readiness_report": readiness
    }

@router.post("/{session_id}/launch")
def launch_runtime_session(session_id: str):
    teams_runtime_service.launch_session(session_id)
    return {"message": "Teams automation client initialized."}

@router.post("/{session_id}/join")
def join_runtime_meeting(session_id: str):
    teams_runtime_service.join_meeting(session_id)
    return {"message": "Teams joining sequence initiated."}

@router.post("/{session_id}/leave")
def leave_runtime_meeting(session_id: str):
    teams_runtime_service.leave_meeting(session_id)
    return {"message": "Teams leave sequence completed."}

@router.post("/{session_id}/speak")
def start_runtime_speaking(session_id: str, req: SpeakRequest):
    speech_runtime_service.speak(session_id, req.narration_text)
    return {"message": "TTS speaking initiated."}

@router.post("/{session_id}/stop-speaking")
def stop_runtime_speaking(session_id: str):
    speech_runtime_service.stop_speaking(session_id)
    return {"message": "TTS speaking interrupted."}

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
        coordinator = runtime_service.get_coordinator(db, session_id)
        answer = await coordinator.inject_question(req.speaker_name, req.question_text)
        
        config = db.query(OrganizationConfig).first()
        trainer = config.ai_trainer_name if config else "KONE Trainer"
        return {
            "question": {
                "speaker": req.speaker_name,
                "text": req.question_text
            },
            "answer": {
                "speaker": trainer,
                "text": answer
            }
        }
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

@router.get("/{session_id}/report")
def download_session_report(session_id: str, db: DBSession = Depends(get_db)):
    try:
        report_path, _ = report_service.generate_and_save_packages(db, session_id)
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="Report file not found")
        return FileResponse(
            path=report_path,
            filename=f"induction_report_{session_id}.md",
            media_type="text/markdown"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/transcript")
def download_session_transcript(session_id: str, db: DBSession = Depends(get_db)):
    try:
        _, transcript_path = report_service.generate_and_save_packages(db, session_id)
        if not transcript_path.exists():
            raise HTTPException(status_code=404, detail="Transcript file not found")
        return FileResponse(
            path=transcript_path,
            filename=f"induction_transcript_{session_id}.md",
            media_type="text/markdown"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/attendance")
def get_attendance_report(session_id: str, db: DBSession = Depends(get_db)):
    from app.services.attendance_service import attendance_service
    return attendance_service.get_attendance_summary(db, session_id)

@router.get("/{session_id}/transcript-data")
def get_transcript_raw(session_id: str, db: DBSession = Depends(get_db)):
    from app.services.transcript_service import transcript_service
    return transcript_service.get_chronological_transcript(db, session_id)

@router.post("/{session_id}/reconnect")
async def trigger_reconnect_simulation(session_id: str):
    from app.services.teams_runtime_service import teams_runtime_service
    await teams_runtime_service.simulate_reconnect(session_id)
    return {"message": "Reconnection sequence triggered."}
