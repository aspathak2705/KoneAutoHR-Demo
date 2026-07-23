import time
from app.modules.presentation_observer.models.observation import Observation
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.presentation_observer.models.observation_state import ObservationState
from typing import List, Dict, Any

class ObservationBuilder:
    @staticmethod
    def build(
        meeting_state: MeetingState,
        presentation_state: PresentationMode,
        current_state: ObservationState,
        events: List[ObservationEvent],
        flags: dict,
        timeline_index: int,
        details: Dict[str, Any] = None
    ) -> Observation:
        """
        Builds a structured immutable Observation data object.
        """
        return Observation(
            timestamp=time.time(),
            meeting_state=meeting_state,
            presentation_state=presentation_state,
            observation_state=current_state,
            events=events,
            slide_changed=flags.get("slide_changed", False),
            presentation_started=flags.get("presentation_started", False),
            presentation_ended=flags.get("presentation_ended", False),
            chat_open=flags.get("chat_open", False),
            participants_open=flags.get("participants_open", False),
            recording_active=flags.get("recording_active", False),
            timeline_index=timeline_index,
            details=details or {}
        )
