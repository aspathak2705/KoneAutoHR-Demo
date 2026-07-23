from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.presentation_observer.models.observation import Observation
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.presentation_observer.observer.observation_context import ObservationContext
from app.modules.presentation_observer.analyzers.state_tracker import state_tracker
from app.modules.presentation_observer.analyzers.change_detector import change_detector
from app.modules.presentation_observer.analyzers.timeline_tracker import timeline_tracker
from app.modules.presentation_observer.observer.observation_builder import ObservationBuilder
from typing import Optional

class PresentationObserver:
    def __init__(self):
        self.context = ObservationContext()
        self.prev_snapshot: Optional[SemanticSnapshot] = None

    def observe(self, snapshot: SemanticSnapshot) -> Observation:
        """
        Receives SemanticSnapshot, updates trackers, registers timeline events, and compiles Observation.
        """
        # 1. State tracking
        current_state = state_tracker.track_state(snapshot)
        
        # 2. Change detection
        events, flags = change_detector.detect_changes(self.prev_snapshot, snapshot, self.context)
        
        # 3. Timeline recording
        timeline_tracker.record_events(events)
        self.context.timeline_position = len(timeline_tracker.get_timeline())
        
        # 4. Assemble Observation
        obs = ObservationBuilder.build(
            meeting_state=snapshot.meeting_state,
            presentation_state=snapshot.presentation_state,
            current_state=current_state,
            events=events,
            flags=flags,
            timeline_index=self.context.timeline_position,
            details=snapshot.details
        )
        
        # Retain snapshot for next comparison cycle
        self.prev_snapshot = snapshot
        return obs

presentation_observer = PresentationObserver()
