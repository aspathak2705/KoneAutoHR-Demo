import time
from typing import Optional
from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.presentation_observer.models.observation import Observation

class ObservationContext:
    def __init__(self):
        # Rolling reference frames
        self.prev_observation: Optional[Observation] = None
        self.prev_snapshot: Optional[SemanticSnapshot] = None
        
        # Timeline and markers tracking
        self.presentation_start_time: Optional[float] = None
        self.last_event_timestamp: float = time.time()
        self.current_timeline_index: int = 0
        
        # Slide Presentation Signature
        self.presentation_signature: Optional[str] = None
