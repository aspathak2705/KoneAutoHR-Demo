from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.presentation_observer.models.observation import Observation
from app.modules.presentation_observer.observer.observation_context import ObservationContext
from loguru import logger
from app.modules.presentation_observer.analyzers.state_tracker import state_tracker
from app.modules.presentation_observer.analyzers.change_detector import change_detector
from app.modules.presentation_observer.analyzers.timeline_tracker import timeline_tracker
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.presentation_observer.observer.observation_builder import ObservationBuilder

class PresentationObserver:
    def __init__(self):
        self.context = ObservationContext()

    def observe(self, snapshot: SemanticSnapshot) -> Observation:
        """
        Receives SemanticSnapshot, updates trackers, registers timeline events, and compiles Observation.
        """
        # 1. State tracking
        current_state = state_tracker.track_state(snapshot)
        
        # 2. Change detection
        events, flags = change_detector.detect_changes(snapshot, self.context)
        
        # 3. Timeline recording
        from app.modules.presentation_observer.config import presentation_observer_config
        for event in events:
            if event != ObservationEvent.NONE:
                self.context.timeline.append(event)
        limit = presentation_observer_config.timeline_size
        if len(self.context.timeline) > limit:
            self.context.timeline = self.context.timeline[-limit:]
        self.context.current_timeline_index = len(self.context.timeline)
        
        # 4. Assemble Observation
        obs = ObservationBuilder.build(
            meeting_state=snapshot.meeting_state,
            presentation_state=snapshot.presentation_state,
            current_state=current_state,
            events=events,
            flags=flags,
            timeline_index=self.context.current_timeline_index,
            details=snapshot.details
        )
        
        # Retain references in context
        self.context.prev_snapshot = snapshot
        self.context.prev_observation = obs
        return obs

    def presentation_detected(self) -> bool:
        """
        Returns True if a Shared PowerPoint or presentation window is visible on screen.
        """
        if not self.context.prev_snapshot:
            logger.debug("PresentationObserver | No previous snapshot found for detection.")
            return False
        from app.modules.semantic_browser.models.presentation_state import PresentationMode
        state = self.context.prev_snapshot.presentation_state
        detected = state in [
            PresentationMode.POWERPOINT_SHARED,
            PresentationMode.SCREEN_SHARING
        ]
        logger.info(f"PresentationObserver | Presentation state: {state} | Detected: {detected}")
        return detected

presentation_observer = PresentationObserver()
