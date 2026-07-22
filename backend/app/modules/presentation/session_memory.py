import datetime
from typing import Dict, List, Any, Optional
from loguru import logger
from app.modules.presentation.session_script_models import SessionMemoryState, SessionExecutionContext

class SessionMemory:
    """
    Sprint 11 & Item 8 — Session Memory & Execution Context
    Tracks runtime session state and exports SessionExecutionContext for Phase 2B.2 handoff and interruption recovery.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_step_index: int = 0
        self.total_steps: int = 0
        self.current_step_type: str = "IDLE"
        self.current_slide: int = 0
        self.participants_count: int = 0
        self.is_paused: bool = False
        self.completed_steps: List[int] = []
        self.pending_steps: List[int] = []
        self.step_history: List[Dict[str, Any]] = []

    def start_session(self, total_steps: int) -> None:
        self.total_steps = total_steps
        self.current_step_index = 0
        self.completed_steps = []
        self.pending_steps = list(range(1, total_steps + 1))
        self.step_history = []
        logger.info(f"SessionMemory | Session {self.session_id} memory initialized with {total_steps} steps.")

    def record_step_start(self, step_id: int, step_type: str) -> None:
        self.current_step_index = step_id
        self.current_step_type = step_type
        if step_id in self.pending_steps:
            self.pending_steps.remove(step_id)
        self.step_history.append({
            "step_id": step_id,
            "type": step_type,
            "status": "STARTED",
            "timestamp": datetime.datetime.now().isoformat()
        })
        logger.info(f"SessionMemory | Step {step_id} ({step_type}) started.")

    def record_step_complete(self, step_id: int, details: Optional[Dict[str, Any]] = None) -> None:
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)
        self.step_history.append({
            "step_id": step_id,
            "type": self.current_step_type,
            "status": "COMPLETED",
            "details": details or {},
            "timestamp": datetime.datetime.now().isoformat()
        })
        logger.info(f"SessionMemory | Step {step_id} completed.")

    def update_participants(self, count: int) -> None:
        self.participants_count = count

    def get_state(self) -> SessionMemoryState:
        return SessionMemoryState(
            session_id=self.session_id,
            current_step_index=self.current_step_index,
            total_steps=self.total_steps,
            current_step_type=self.current_step_type,
            current_slide=self.current_slide,
            participants_count=self.participants_count,
            is_paused=self.is_paused,
            completed_steps=self.completed_steps
        )

    def get_execution_context(self) -> SessionExecutionContext:
        return SessionExecutionContext(
            session_id=self.session_id,
            current_script_step=self.current_step_index,
            completed_steps=self.completed_steps,
            pending_steps=self.pending_steps,
            current_runtime_state=self.current_step_type,
            current_slide=self.current_slide,
            participants_count=self.participants_count
        )
