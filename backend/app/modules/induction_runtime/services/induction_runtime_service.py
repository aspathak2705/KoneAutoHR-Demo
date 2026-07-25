from typing import Dict, Any, Optional
from sqlalchemy.orm import Session as DBSession
from app.modules.induction_runtime.orchestrator.runtime_coordinator import RuntimeCoordinator
from loguru import logger

class InductionRuntimeService:
    """
    Provides access to RuntimeCoordinator instances.
    Coordinates induction runtime lifecycle.
    """
    def __init__(self):
        # Maps session_id -> active RuntimeCoordinator instance
        self._active_coordinators: Dict[str, RuntimeCoordinator] = {}

    def create_coordinator(self, db: DBSession, session_id: str, runtime_id: Optional[str] = None) -> RuntimeCoordinator:
        """
        Creates a new RuntimeCoordinator for the given session.
        If runtime_id not provided, a new Runtime entry will be created.
        """
        logger.info(f"InductionRuntimeService | START create_coordinator for session {session_id}")
        
        try:
            if runtime_id:
                coordinator = RuntimeCoordinator(db, session_id, runtime_id=runtime_id)
            else:
                # Create new runtime entry via RuntimeService
                from app.services.runtime_service import runtime_service
                coordinator = runtime_service.create_runtime_and_coordinator(db, session_id)
            
            self._active_coordinators[session_id] = coordinator
            logger.info(f"InductionRuntimeService | SUCCESS created coordinator for session {session_id}")
            return coordinator
        except Exception as e:
            logger.error(f"InductionRuntimeService | FAILED create_coordinator: {e}")
            raise

    def get_coordinator(self, db: DBSession, session_id: str) -> RuntimeCoordinator:
        """
        Retrieves or initializes the RuntimeCoordinator for the given session.
        """
        if session_id not in self._active_coordinators:
            logger.info(f"InductionRuntimeService | Coordinator not cached for {session_id}, creating new one")
            self.create_coordinator(db, session_id)
        return self._active_coordinators[session_id]

    def remove_coordinator(self, session_id: str) -> None:
        """
        Clears coordinator from cache when session completes.
        """
        self._active_coordinators.pop(session_id, None)
        logger.info(f"InductionRuntimeService | Removed coordinator cache for session {session_id}")

induction_runtime_service = InductionRuntimeService()
