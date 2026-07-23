from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.presentation_observer.config import presentation_observer_config
from typing import List

class TimelineTracker:
    def __init__(self):
        self._timeline: List[ObservationEvent] = []

    def record_events(self, events: List[ObservationEvent]) -> None:
        """
        Appends new events to the timeline history queue and caps it.
        """
        for event in events:
            if event != ObservationEvent.NONE:
                self._timeline.append(event)
                
        limit = presentation_observer_config.timeline_size
        if len(self._timeline) > limit:
            self._timeline = self._timeline[-limit:]

    def get_timeline(self) -> List[ObservationEvent]:
        return self._timeline

    def clear(self) -> None:
        self._timeline = []

timeline_tracker = TimelineTracker()
