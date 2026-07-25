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
from loguru import logger

router = APIRouter(prefix="/runtime", tags=["Orchestration Runtime"])

# ============================================================================
# LOCKED LIFECYCLE ENDPOINTS - NEW ARCHITECTURE
# ============================================================================

@router.post("/{session_id}/prepare")
async def prepare_runtime(session_id: str, db: DBSession = Depends(get_db)):
    """
    Lifecycle Phase 1: NOT_CREATED → PREPARING → READY
    
    Button: "Prepare Runtime"
    Responsibilities:
    - Create Runtime entry
    - Load Configuration
    - Verify Assets (presentation, script, faq)
    - Verify Meeting URL
    - Verify Browser Installation
    - Register Runtime in READY state
    """
    logger.info(f"API | START POST /prepare for session {session_id}")
    try:
        # Create runtime and coordinator
        coordinator = runtime_service.create_runtime_and_coordinator(db, session_id)
        
        # Prepare runtime (PREPARING → READY)
        if not await coordinator.prepare_runtime():
            raise HTTPException(status_code=400, detail="Failed to prepare runtime")
        
        logger.info(f"API | SUCCESS POST /prepare - runtime READY")
        return {
            "message": "Runtime prepared successfully",
            "state": "READY",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"API | FAILED POST /prepare: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/start-induction")
async def start_induction(session_id: str, db: DBSession = Depends(get_db)):
    """
    Lifecycle Phase 2: READY → STARTING → BROWSER_READY
    
    Button: "Start Induction" (part of the READY button flow)
    Responsibilities:
    - Launch Browser (MOVED HERE from prepare_runtime)
    - Open Teams in browser
    - Transition to BROWSER_READY
    """
    logger.info(f"API | START POST /start-induction for session {session_id}")
    try:
        coordinator = runtime_service.get_coordinator(db, session_id)
        
        # Start induction (READY → BROWSER_READY)
        if not await coordinator.start_induction():
            raise HTTPException(status_code=400, detail="Failed to start induction")
        
        logger.info(f"API | SUCCESS POST /start-induction - browser READY")
        return {
            "message": "Induction started, browser ready",
            "state": "BROWSER_READY",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"API | FAILED POST /start-induction: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/join-meeting")
async def join_meeting_endpoint(session_id: str, db: DBSession = Depends(get_db)):
    """
    Lifecycle Phase 3: BROWSER_READY → JOINING → WAITING → CONNECTED
    
    Button: "Join Meeting" (part of the READY button flow)
    Responsibilities:
    - Get meeting URL
    - Open Teams meeting
    - Configure devices
    - Join meeting
    - Wait for presentation
    - Transition to CONNECTED
    """
    logger.info(f"API | START POST /join-meeting for session {session_id}")
    try:
        coordinator = runtime_service.get_coordinator(db, session_id)
        
        # Get meeting URL from context
        context = runtime_service.get_runtime_context(db, session_id)
        meeting_url = context.get("meeting", {}).get("teams_meeting_url")
        
        if not meeting_url:
            raise HTTPException(status_code=400, detail="Meeting URL not found")
        
        # Join meeting
        if not await coordinator.join_meeting(meeting_url):
            raise HTTPException(status_code=400, detail="Failed to join meeting")
        
        logger.info(f"API | SUCCESS POST /join-meeting - CONNECTED")
        return {
            "message": "Joined meeting successfully",
            "state": "CONNECTED",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"API | FAILED POST /join-meeting: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/end")
async def end_runtime(session_id: str, db: DBSession = Depends(get_db)):
    """
    Lifecycle Phase Final: Any state → FINISHING → STOPPED
    
    Button: "End Session"
    Responsibilities:
    - Leave meeting
    - Stop presentation
    - Cleanup resources in reverse order
    - Transition to STOPPED
    """
    logger.info(f"API | START POST /end for session {session_id}")
    try:
        coordinator = runtime_service.get_coordinator(db, session_id)
        
        # Finish presentation and cleanup
        if not await coordinator.finish_presentation():
            raise HTTPException(status_code=400, detail="Failed to finish presentation")
        
        # Remove from cache
        runtime_service.remove_coordinator(session_id)
        
        logger.info(f"API | SUCCESS POST /end - STOPPED")
        return {
            "message": "Runtime stopped successfully",
            "state": "STOPPED",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"API | FAILED POST /end: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================================
# LEGACY ENDPOINTS (kept for backward compatibility during migration)
# ============================================================================

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
        "last_error": db_runtime.last_error if db_runtime else None,
        "questions_asked": len(questions),
        "presentation_ready": readiness.get("has_presentation") and readiness.get("has_script") and readiness.get("has_faq"),
        "employees_ready": readiness.get("has_employees"),
        "meeting_ready": readiness.get("has_meeting"),
        "ai_ready": readiness.get("has_script") and readiness.get("has_faq"),
        "readiness_report": readiness
    }

@router.post("/{session_id}/launch")
async def launch_runtime_session(session_id: str):
    try:
        result = await teams_runtime_service.launch_session(session_id)
        return {"message": "Teams automation client initialized.", "runtime": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/join")
async def join_runtime_meeting(session_id: str):
    try:
        result = await teams_runtime_service.join_meeting(session_id)
        return {"message": "Teams joining sequence initiated.", "runtime": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/leave")
async def leave_runtime_meeting(session_id: str):
    try:
        result = await teams_runtime_service.leave_meeting(session_id)
        return {"message": "Teams leave sequence completed.", "runtime": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/speak")
async def start_runtime_speaking(session_id: str, req: SpeakRequest):
    speech_runtime_service.speak(session_id, req.narration_text)
    return {"message": "TTS speaking initiated."}

@router.post("/{session_id}/stop-speaking")
async def stop_runtime_speaking(session_id: str):
    speech_runtime_service.stop_speaking(session_id)
    return {"message": "TTS speaking interrupted."}

@router.post("/{session_id}/start")
async def start_runtime(session_id: str, db: DBSession = Depends(get_db)):
    meeting_runtime_service.start_meeting(session_id)
    return {"message": "AI meeting orchestration session launched."}

@router.post("/{session_id}/stop")
async def stop_runtime(session_id: str, db: DBSession = Depends(get_db)):
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
