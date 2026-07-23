from app.modules.induction_runtime.models.runtime_state import RuntimeState
from loguru import logger

class RuntimeSessionManager:
    def __init__(self):
        self.state: RuntimeState = RuntimeState.CREATED

    def set_state(self, new_state: RuntimeState) -> None:
        """
        Transitions session state.
        """
        old_state = self.state
        if old_state != new_state:
            self.state = new_state
            logger.info(f"RuntimeSessionManager | State transitioned: {old_state.value} -> {new_state.value}")

    def is_active(self) -> bool:
        """
        Returns true if the session is currently presenting or answering questions.
        """
        return self.state in [
            RuntimeState.INTRODUCTION,
            RuntimeState.PRESENTING,
            RuntimeState.QUESTION_ANSWER
        ]
