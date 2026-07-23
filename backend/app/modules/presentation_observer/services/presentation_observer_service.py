from app.modules.semantic_browser.services.semantic_browser_service import semantic_browser_service
from app.modules.presentation_observer.observer.presentation_observer import presentation_observer
from app.modules.presentation_observer.models.observation import Observation
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.presentation_observer.analyzers.timeline_tracker import timeline_tracker
from typing import Optional, List

class PresentationObserverService:
    def __init__(self):
        self._latest_observation: Optional[Observation] = None

    async def run_observation_cycle(self) -> Observation:
        """
        Executes one scan loop: pulls SemanticSnapshot and updates observation context.
        """
        snapshot = await semantic_browser_service.get_snapshot()
        self._latest_observation = presentation_observer.observe(snapshot)
        return self._latest_observation

    def get_latest_observation(self) -> Optional[Observation]:
        """
        Retrieves the latest cached Observation frame.
        """
        return self._latest_observation

    def get_timeline(self) -> List[ObservationEvent]:
        """
        Retrieves the rolling call event timeline.
        """
        return timeline_tracker.get_timeline()

presentation_observer_service = PresentationObserverService()
