from typing import Dict, Any, Optional
from sqlalchemy.orm import Session as DBSession
from app.modules.induction_runtime.orchestrator.runtime_coordinator import RuntimeCoordinator
from loguru import logger

class InductionRuntimeService:
    def __init__(self):
        # Maps session_id -> active RuntimeCoordinator instance
        self._active_coordinators: Dict[str, RuntimeCoordinator] = {}

    def get_coordinator(self, db: DBSession, session_id: str) -> RuntimeCoordinator:
        """
        Retrieves or initializes the RuntimeCoordinator for the given session.
        """
        if session_id not in self._active_coordinators:
            coordinator = RuntimeCoordinator(db, session_id)
            coordinator.initialize()
            self._active_coordinators[session_id] = coordinator
            logger.info(f"InductionRuntimeService | Initialized and cached coordinator for session {session_id}")
        return self._active_coordinators[session_id]

    def remove_coordinator(self, session_id: str) -> None:
        """
        Clears coordinator from cache when session completes.
        """
        self._active_coordinators.pop(session_id, None)
        logger.info(f"InductionRuntimeService | Removed coordinator cache for session {session_id}")

induction_runtime_service = InductionRuntimeService()
