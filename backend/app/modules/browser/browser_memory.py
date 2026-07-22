from typing import Optional

class BrowserMemory:
    """
    Module 5 — Browser Memory
    Maintains a record of browser-side states, retry counters, and navigation parameters.
    """
    def __init__(self):
        self.current_page_state: str = "INITIALIZING"
        self.meeting_url: Optional[str] = None
        self.last_action: Optional[str] = None
        self.retry_count: int = 0
        self.is_presentation_shared: bool = False

    def update_state(self, state: str) -> None:
        self.current_page_state = state

    def record_action(self, action_name: str) -> None:
        self.last_action = action_name
        self.retry_count = 0

    def increment_retry(self) -> int:
        self.retry_count += 1
        return self.retry_count

browser_memory = BrowserMemory()
