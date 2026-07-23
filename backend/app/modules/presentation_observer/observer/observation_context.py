import time
from typing import Optional
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode

class ObservationContext:
    def __init__(self):
        self.current_slide: Optional[str] = None
        self.presentation_mode: PresentationMode = PresentationMode.NONE
        self.meeting_state: MeetingState = MeetingState.DISCONNECTED
        self.last_change_time: float = time.time()
        self.timeline_position: int = 0
        self.presentation_started: bool = False
        self.presentation_finished: bool = False
        
        # Internal tracker to detect slide changes (saves text hashes or label of slide container elements)
        self.slide_elements_hash: str = ""
