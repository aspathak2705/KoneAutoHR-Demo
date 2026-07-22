import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.modules.session.session_interpreter import get_session_interpreter
from app.modules.presentation.models import PresentationStatusResponse

router = APIRouter(prefix="/runtime", tags=["Session Engine"])

@router.post("/{session_id}/presentation/start")
def start_session_engine(session_id: str, db: Session = Depends(get_db)):
    """
    POST /api/v1/runtime/{id}/presentation/start
    Triggers autonomous HR induction session run for specified session.
    """
    interpreter = get_session_interpreter(session_id)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(interpreter.start_session(db))
    except RuntimeError:
        asyncio.run(interpreter.start_session(db))

    return {"status": "success", "message": f"HR induction session started for session {session_id}"}

@router.post("/{session_id}/presentation/pause")
def pause_session_engine(session_id: str):
    """
    POST /api/v1/runtime/{id}/presentation/pause
    Pauses active session execution.
    """
    interpreter = get_session_interpreter(session_id)
    interpreter.pause_session()
    return {"status": "success", "message": f"Induction session paused for session {session_id}"}

@router.post("/{session_id}/presentation/resume")
def resume_session_engine(session_id: str):
    """
    POST /api/v1/runtime/{id}/presentation/resume
    Resumes paused session.
    """
    interpreter = get_session_interpreter(session_id)
    interpreter.resume_session()
    return {"status": "success", "message": f"Induction session resumed for session {session_id}"}

@router.post("/{session_id}/presentation/stop")
def stop_session_engine(session_id: str):
    """
    POST /api/v1/runtime/{id}/presentation/stop
    Stops session run.
    """
    interpreter = get_session_interpreter(session_id)
    interpreter.stop_session()
    return {"status": "success", "message": f"Induction session stopped for session {session_id}"}

@router.get("/{session_id}/presentation/status", response_model=PresentationStatusResponse)
def get_session_status(session_id: str):
    """
    GET /api/v1/runtime/{id}/presentation/status
    Returns real-time session progress and memory state.
    """
    interpreter = get_session_interpreter(session_id)
    state = interpreter.memory.get_state()
    
    return PresentationStatusResponse(
        session_id=session_id,
        presentation_state=state.current_step_type,
        current_slide=state.current_slide,
        total_slides=state.total_steps,
        is_active=interpreter._is_running,
        current_narration=f"Step {state.current_step_index}: {state.current_step_type}",
        last_action=state.current_step_type
    )
