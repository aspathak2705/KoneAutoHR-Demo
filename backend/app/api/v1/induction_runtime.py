from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Dict, Any

from app.db.database import get_db
from app.modules.induction_runtime.services.induction_runtime_service import induction_runtime_service

router = APIRouter(prefix="/induction-runtime", tags=["AI Induction Runtime Engine"])

class InjectQuestionRequest(BaseModel):
    speaker: str
    question: str

@router.post("/{session_id}/initialize")
def initialize_runtime(session_id: str, db: DBSession = Depends(get_db)):
    try:
        coord = induction_runtime_service.get_coordinator(db, session_id)
        return {"status": "INITIALIZED", "session_id": session_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Initialization failed: {str(e)}"
        )

@router.get("/{session_id}/status")
def get_runtime_status(session_id: str, db: DBSession = Depends(get_db)):
    try:
        coord = induction_runtime_service.get_coordinator(db, session_id)
        memory_report = coord.memory.get_memory_report()
        return {
            "session_id": session_id,
            "runtime_state": coord.session_manager.state.value,
            "speaker_turn": coord.conversation_orchestrator.determine_next_speaker(coord.session_manager.state),
            "memory": memory_report
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch status: {str(e)}"
        )

@router.post("/{session_id}/inject-question")
async def inject_chat_question(session_id: str, req: InjectQuestionRequest, db: DBSession = Depends(get_db)):
    try:
        coord = induction_runtime_service.get_coordinator(db, session_id)
        answer = await coord.inject_question(req.speaker, req.question)
        return {
            "session_id": session_id,
            "question": req.question,
            "answer": answer
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to inject question: {str(e)}"
        )
