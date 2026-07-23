from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.presentation_observer.models.observation_state import ObservationState

class Observation(BaseModel):
    timestamp: float
    meeting_state: MeetingState
    presentation_state: PresentationMode
    current_state: ObservationState
    events: List[ObservationEvent] = []
    
    # Changes flags
    slide_changed: bool = False
    presentation_started: bool = False
    presentation_ended: bool = False
    chat_open: bool = False
    participants_open: bool = False
    recording: bool = False
    
    timeline_index: int = 0
    details: Dict[str, Any] = {}
