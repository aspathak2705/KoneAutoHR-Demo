from typing import Optional, List, Dict, Any
from app.modules.meeting_bot.bot.bot_state import BotState

class MeetingBotContext:
    def __init__(self):
        self.meeting_url: Optional[str] = None
        self.participants: List[str] = []
        self.audio_state: Dict[str, Any] = {"playing": False, "track": None}
        self.chat_messages: List[Dict[str, Any]] = []
        self.last_screenshot_path: Optional[str] = None
        self.state: BotState = BotState.CREATED
        
        # Playwright native runtime handles
        self.playwright = None
        self.browser = None
        self.browser_context = None
        self.page = None

    def to_dict(self) -> dict:
        return {
            "meeting_url": self.meeting_url,
            "participants": self.participants,
            "audio_state": self.audio_state,
            "chat_messages": self.chat_messages,
            "last_screenshot_path": self.last_screenshot_path,
            "state": self.state.value
        }
