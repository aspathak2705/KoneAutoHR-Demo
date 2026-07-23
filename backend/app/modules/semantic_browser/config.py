import os

class SemanticBrowserConfig:
    def __init__(self):
        # Polling frequency in seconds
        self.poll_interval: float = float(os.environ.get("SEMANTIC_POLL_INTERVAL", "1.0"))
        
        # Max snapshots to retain in memory history
        self.history_size: int = int(os.environ.get("SEMANTIC_HISTORY_SIZE", "10"))
        
        # Feature toggles
        self.enable_accessibility: bool = os.environ.get("SEMANTIC_ENABLE_ACCESSIBILITY", "true").lower() == "true"
        self.enable_dom: bool = os.environ.get("SEMANTIC_ENABLE_DOM", "true").lower() == "true"
        self.enable_presentation: bool = os.environ.get("SEMANTIC_ENABLE_PRESENTATION", "true").lower() == "true"

semantic_browser_config = SemanticBrowserConfig()
