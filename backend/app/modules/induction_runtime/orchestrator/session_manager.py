from app.modules.induction_runtime.models.runtime_state import RuntimeState
from typing import Optional
from loguru import logger
from sqlalchemy.orm import Session as DBSession
import asyncio

class RuntimeSessionManager:
    """
    State Machine Guard - LOCKED State Machine with Runtime Locking.
    
    CRITICAL RULES:
    - The RuntimeSessionManager ONLY tracks runtime state and validates state transitions.
    - It does NOT invoke other components or trigger side effects.
    - All state transitions must follow the locked sequence.
    - All transitions must be persisted to the database.
    - Every transition logs START, SUCCESS, or FAILED.
    - Runtime locking prevents duplicate concurrent operations.
    - RuntimeSessionManager is the SOLE authority for lifecycle state.
    - MeetingBot MUST NOT update runtime state directly.
    """
    def __init__(self, db: Optional[DBSession] = None, runtime_id: Optional[str] = None):
        self.state: RuntimeState = RuntimeState.NOT_CREATED
        self.db = db
        self.runtime_id = runtime_id
        self.last_error: Optional[str] = None
        
        # Runtime locking to prevent concurrent state changes
        self._transition_lock = asyncio.Lock()

    def can_transition(self, target_state: RuntimeState) -> bool:
        """
        Validates state machine progression guards.
        
        LOCKED TRANSITION RULES (no new states, no deviations):
        NOT_CREATED -> PREPARING
        PREPARING -> READY
        READY -> STARTING
        STARTING -> BROWSER_READY
        BROWSER_READY -> JOINING
        JOINING -> WAITING
        WAITING -> CONNECTED
        CONNECTED -> PRESENTING
        PRESENTING -> FINISHED
        FINISHED -> STOPPING
        STOPPING -> STOPPED
        
        Any state -> FAILED (error recovery path)
        """
        current = self.state
        
        # Identity transition is always allowed
        if current == target_state:
            return True
        
        # Locked forward progression path
        valid_transitions = {
            RuntimeState.NOT_CREATED: [RuntimeState.PREPARING, RuntimeState.FAILED],
            RuntimeState.PREPARING: [RuntimeState.READY, RuntimeState.FAILED],
            RuntimeState.READY: [RuntimeState.STARTING, RuntimeState.FINISHED, RuntimeState.FAILED],
            RuntimeState.STARTING: [RuntimeState.BROWSER_READY, RuntimeState.FINISHED, RuntimeState.FAILED],
            RuntimeState.BROWSER_READY: [RuntimeState.JOINING, RuntimeState.FINISHED, RuntimeState.FAILED],
            RuntimeState.JOINING: [RuntimeState.WAITING, RuntimeState.FINISHED, RuntimeState.FAILED],
            RuntimeState.WAITING: [RuntimeState.CONNECTED, RuntimeState.FINISHED, RuntimeState.FAILED],
            RuntimeState.CONNECTED: [RuntimeState.PRESENTING, RuntimeState.FINISHED, RuntimeState.FAILED],
            RuntimeState.PRESENTING: [RuntimeState.FINISHED, RuntimeState.FAILED],
            RuntimeState.FINISHED: [RuntimeState.STOPPING, RuntimeState.FAILED],
            RuntimeState.STOPPING: [RuntimeState.STOPPED, RuntimeState.FAILED],
            RuntimeState.STOPPED: [],  # Terminal state
            RuntimeState.FAILED: [RuntimeState.STOPPING],  # Recovery path
        }
        
        if current not in valid_transitions:
            return False
            
        return target_state in valid_transitions[current]

    async def transition_to(self, target_state: RuntimeState, error_msg: Optional[str] = None) -> bool:
        """
        Performs and records the state transition if validated by transition guards.
        THREAD-SAFE via asyncio.Lock to prevent concurrent state changes.
        Persists to database if runtime_id provided.
        Logs START, SUCCESS, or FAILED for every transition.
        """
        async with self._transition_lock:
            logger.info(f"RuntimeSessionManager | START transition: {self.state.value} -> {target_state.value}")
            
            if not self.can_transition(target_state):
                logger.warning(f"RuntimeSessionManager | FAILED invalid transition: {self.state.value} -> {target_state.value}")
                return False
            
            try:
                old_state = self.state
                self.state = target_state
                
                if error_msg:
                    self.last_error = error_msg
                
                # Persist to database if available
                if self.db and self.runtime_id:
                    self._persist_state_transition(old_state, target_state, error_msg)
                
                logger.info(f"RuntimeSessionManager | SUCCESS transition: {old_state.value} -> {target_state.value}")
                return True
            except Exception as e:
                logger.error(f"RuntimeSessionManager | FAILED to transition to {target_state.value}: {e}")
                return False

    def _persist_state_transition(self, old_state: RuntimeState, new_state: RuntimeState, error_msg: Optional[str] = None) -> None:
        """
        Persists state transition to database.
        """
        try:
            from app.models.runtime import Runtime
            runtime = self.db.query(Runtime).filter(Runtime.id == self.runtime_id).first()
            if runtime:
                runtime.state = new_state.value
                if error_msg:
                    runtime.last_error = error_msg
                self.db.commit()
                logger.debug(f"RuntimeSessionManager | Persisted state transition to DB: {new_state.value}")
        except Exception as e:
            logger.error(f"RuntimeSessionManager | Failed to persist state to DB: {e}")

    def is_active(self) -> bool:
        """
        Returns true if the runtime is in an active execution state.
        """
        return self.state in [
            RuntimeState.STARTING,
            RuntimeState.BROWSER_READY,
            RuntimeState.JOINING,
            RuntimeState.WAITING,
            RuntimeState.CONNECTED,
            RuntimeState.PRESENTING,
        ]

    def is_terminal(self) -> bool:
        """
        Returns true if the runtime is in a terminal state.
        """
        return self.state in [
            RuntimeState.STOPPED,
            RuntimeState.FAILED,
        ]
