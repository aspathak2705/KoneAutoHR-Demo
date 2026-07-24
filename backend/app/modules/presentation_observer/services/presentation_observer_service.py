from app.modules.semantic_browser.services.semantic_browser_service import semantic_browser_service
from app.modules.presentation_observer.observer.presentation_observer import PresentationObserver
from app.modules.presentation_observer.models.observation import Observation
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from typing import Optional, List, Dict

class PresentationObserverService:
    def __init__(self):
        # registry of session observers to guarantee session isolation
        self._observers: Dict[str, PresentationObserver] = {}

    def get_observer(self, session_id: str) -> PresentationObserver:
        if session_id not in self._observers:
            self._observers[session_id] = PresentationObserver()
        return self._observers[session_id]

    async def run_observation_cycle(self, session_id: str) -> Observation:
        """
        Executes one scan loop: pulls SemanticSnapshot and updates observation context.
        """
        snapshot = await semantic_browser_service.get_snapshot(session_id)
        observer = self.get_observer(session_id)
        obs = observer.observe(snapshot)
        return obs

    def get_latest_observation(self, session_id: str) -> Optional[Observation]:
        """
        Retrieves the latest cached Observation frame.
        """
        observer = self.get_observer(session_id)
        return observer.context.prev_observation

    def get_timeline(self, session_id: str) -> List[ObservationEvent]:
        """
        Retrieves the rolling call event timeline.
        """
        observer = self.get_observer(session_id)
        return observer.context.timeline

    def remove_observer(self, session_id: str) -> None:
        """
        Explicitly disposes the observer context on session shutdown.
        """
        self._observers.pop(session_id, None)

presentation_observer_service = PresentationObserverService()
