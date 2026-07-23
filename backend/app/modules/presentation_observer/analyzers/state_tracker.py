from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.presentation_observer.models.observation_state import ObservationState
from loguru import logger

class StateTracker:
    def track_state(self, snapshot: SemanticSnapshot) -> ObservationState:
        """
        Determines current high-level Presentation/Meeting state from snapshot metrics.
        """
        meeting = snapshot.meeting_state
        pres = snapshot.presentation_state

        if meeting == MeetingState.LOBBY:
            return ObservationState.WAITING
        elif meeting == MeetingState.CONNECTING:
            return ObservationState.LOADING
        elif meeting == MeetingState.DISCONNECTED:
            return ObservationState.ENDED
        
        # Connected state evaluations
        if pres in [PresentationMode.POWERPOINT_SHARED, PresentationMode.SCREEN_SHARING]:
            return ObservationState.ACTIVE
        elif pres == PresentationMode.ENDED:
            return ObservationState.ENDED
        elif pres == PresentationMode.LOADING:
            return ObservationState.LOADING
        elif pres == PresentationMode.WAITING_SCREEN:
            return ObservationState.WAITING
        else:
            return ObservationState.LOST

state_tracker = StateTracker()
