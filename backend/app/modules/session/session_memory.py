from typing import List
from app.modules.presentation.session_script_models import SessionMemoryState, SessionExecutionContext

class SessionMemory:
    """
    Maintains memory of step executions during runtime.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_step_index = 0
        self.total_steps = 0
        self.current_step_type = "IDLE"
        self.current_slide = 1
        self.completed_steps: List[int] = []
        self.is_paused = False

    def start_session(self, total_steps: int) -> None:
        self.total_steps = total_steps
        self.current_step_index = 1
        self.completed_steps.clear()

    def record_step_start(self, step_id: int, step_type: str) -> None:
        self.current_step_index = step_id
        self.current_step_type = step_type

    def record_step_complete(self, step_id: int) -> None:
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)

    def get_execution_context(self) -> SessionExecutionContext:
        pending = [i for i in range(1, self.total_steps + 1) if i not in self.completed_steps]
        return SessionExecutionContext(
            session_id=self.session_id,
            current_script_step=self.current_step_index,
            completed_steps=self.completed_steps,
            pending_steps=pending,
            current_runtime_state=self.current_step_type,
            current_slide=self.current_slide,
            participants_count=0
        )
