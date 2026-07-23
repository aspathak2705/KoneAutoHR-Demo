import os

class PresentationObserverConfig:
    def __init__(self):
        # Polling frequency in seconds
        self.poll_interval: float = float(os.environ.get("OBSERVER_POLL_INTERVAL", "1.0"))
        
        # Max history elements inside the timeline tracker
        self.timeline_size: int = int(os.environ.get("OBSERVER_TIMELINE_SIZE", "50"))
        
        # Feature toggles
        self.enable_change_detection: bool = os.environ.get("OBSERVER_ENABLE_CHANGE_DETECTION", "true").lower() == "true"
        self.enable_timeline: bool = os.environ.get("OBSERVER_ENABLE_TIMELINE", "true").lower() == "true"
        self.enable_state_tracking: bool = os.environ.get("OBSERVER_ENABLE_STATE_TRACKING", "true").lower() == "true"

presentation_observer_config = PresentationObserverConfig()
