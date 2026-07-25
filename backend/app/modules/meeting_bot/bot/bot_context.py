from typing import Optional, List, Dict, Any
from app.modules.meeting_bot.bot.bot_state import BotState

class MeetingBotContext:
    def __init__(self):
        self.meeting_url: Optional[str] = None
        self.participants: List[str] = []
        self.audio_state: Dict[str, Any] = {"playing": False, "track": None}
        self.chat_messages: List[Dict[str, Any]] = []
        self.last_screenshot_path: Optional[str] = None
        self._state: BotState = BotState.CREATED
        self.session_id: Optional[str] = None

    @property
    def state(self) -> BotState:
        return self._state

    @state.setter
    def state(self, value: BotState):
        self._state = value
        if self.session_id:
            try:
                from app.db.database import SessionLocal
                from app.models.runtime import Runtime
                from loguru import logger
                with SessionLocal() as db:
                    runtime = db.query(Runtime).filter(Runtime.session_id == self.session_id).first()
                    if not runtime:
                        runtime = Runtime(session_id=self.session_id, state=value.value, current_slide=0)
                        db.add(runtime)
                    else:
                        runtime.state = value.value
                    db.commit()
                    logger.info(f"MeetingBotContext | Synchronized DB state for session {self.session_id} to: {value.value}")
            except Exception as db_err:
                from loguru import logger
                logger.error(f"MeetingBotContext | Failed to sync DB state: {db_err}")
        
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
