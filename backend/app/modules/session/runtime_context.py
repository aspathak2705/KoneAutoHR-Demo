import threading
from typing import Dict, Any, List, Optional
from loguru import logger

class RuntimeContext:
    """
    Module 10 — Runtime Context
    Centralized thread-safe context storing meeting, browser, presentation, and conversation status.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._lock = threading.Lock()
        
        # Core details
        self.company_name: str = "KONE"
        self.meeting_url: str = ""
        self.guest_name: str = "KONE AI Trainer"
        self.presentation_asset_id: str = ""
        
        # Operational goals
        self.current_goal: str = "INITIALIZING"
        self.runtime_state: str = "INITIALIZING"
        
        # Sub-system metrics
        self.browser_state: str = "UNKNOWN"
        self.is_presentation_shared: bool = False
        self.current_slide: int = 1
        self.is_speaking: bool = False
        self.active_narration: str = ""
        
        # Audit & planner traces
        self.executed_actions: List[str] = []
        self.observed_elements: List[str] = []
        self.failures: List[str] = []
        self.successful_patterns: List[str] = []
        self.session_variables: Dict[str, Any] = {}

    def update(self, **kwargs) -> None:
        with self._lock:
            for key, val in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, val)
                    logger.debug(f"RuntimeContext | Updated {key} -> {val}")
                else:
                    self.session_variables[key] = val

    def get_context_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "current_goal": self.current_goal,
                "runtime_state": self.runtime_state,
                "browser_state": self.browser_state,
                "is_presentation_shared": self.is_presentation_shared,
                "current_slide": self.current_slide,
                "is_speaking": self.is_speaking,
                "active_narration": self.active_narration,
                "executed_actions": list(self.executed_actions),
                "failures": list(self.failures),
                "session_variables": dict(self.session_variables)
            }
