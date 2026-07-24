from app.modules.induction_runtime.models.runtime_state import RuntimeState
from loguru import logger

class RuntimeSessionManager:
    """
    State Machine Guard.
    CRITICAL RULE: The RuntimeSessionManager ONLY tracks runtime state and validates state transitions.
    It does NOT invoke other components or trigger side effects.
    """
    def __init__(self):
        self.state: RuntimeState = RuntimeState.CREATED

    def can_transition(self, target_state: RuntimeState) -> bool:
        """
        Validates state machine progression guards.
        """
        current = self.state
        
        # Identity transition is always allowed
        if current == target_state:
            return True
            
        # Standard workflow:
        # CREATED -> WAITING_FOR_PRESENTATION -> INTRODUCTION -> PRESENTING -> QUESTION_ANSWER -> COMPLETED
        if current == RuntimeState.CREATED:
            return target_state in [RuntimeState.WAITING_FOR_PRESENTATION, RuntimeState.COMPLETED]
            
        if current == RuntimeState.WAITING_FOR_PRESENTATION:
            return target_state in [RuntimeState.INTRODUCTION, RuntimeState.COMPLETED]
            
        if current == RuntimeState.INTRODUCTION:
            return target_state in [RuntimeState.PRESENTING, RuntimeState.COMPLETED]
            
        if current == RuntimeState.PRESENTING:
            return target_state in [RuntimeState.QUESTION_ANSWER, RuntimeState.COMPLETED]
            
        if current == RuntimeState.QUESTION_ANSWER:
            return target_state == RuntimeState.COMPLETED
            
        if current == RuntimeState.COMPLETED:
            # Terminal state, no further transitions allowed
            return False
            
        return False

    def transition_to(self, target_state: RuntimeState) -> bool:
        """
        Performs and records the state transition if validated by transition guards.
        """
        if not self.can_transition(target_state):
            logger.warning(f"RuntimeSessionManager | Blocked invalid transition: {self.state.value} -> {target_state.value}")
            return False
            
        old_state = self.state
        self.state = target_state
        logger.info(f"RuntimeSessionManager | State transitioned: {old_state.value} -> {target_state.value}")
        return True

    def is_active(self) -> bool:
        """
        Returns true if the session is currently active.
        """
        return self.state in [
            RuntimeState.INTRODUCTION,
            RuntimeState.PRESENTING,
            RuntimeState.QUESTION_ANSWER
        ]
