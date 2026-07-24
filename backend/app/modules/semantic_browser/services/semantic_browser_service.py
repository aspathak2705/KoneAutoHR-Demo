from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.semantic_browser.browser.semantic_browser import semantic_browser
from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.semantic_browser.models.semantic_state import DOMSummary
from app.modules.semantic_browser.config import semantic_browser_config
from typing import List, Dict

class SemanticBrowserService:
    def __init__(self):
        self._histories: Dict[str, List[SemanticSnapshot]] = {}

    def _get_history_list(self, session_id: str) -> List[SemanticSnapshot]:
        if session_id not in self._histories:
            self._histories[session_id] = []
        return self._histories[session_id]

    async def get_snapshot(self, session_id: str) -> SemanticSnapshot:
        """
        Coordinates generating a complete current context SemanticSnapshot.
        Retains rolling history in memory per session.
        """
        bot = meeting_bot_service.get_bot(session_id)
        page = bot.context.page
        if not page:
            raise ValueError(f"SemanticBrowserService | Active browser page session not found for Session: {session_id}")
            
        snap = await semantic_browser.generate_snapshot(page)
        
        # Maintain in-memory history list per session
        history = self._get_history_list(session_id)
        history.append(snap)
        limit = semantic_browser_config.history_size
        if len(history) > limit:
            history = history[-limit:]
        self._histories[session_id] = history
            
        return snap

    def get_history(self, session_id: str) -> List[SemanticSnapshot]:
        """
        Returns rolling history list of snapshots for a session.
        """
        return self._get_history_list(session_id)

    async def get_meeting_state(self, session_id: str) -> MeetingState:
        snap = await self.get_snapshot(session_id)
        return snap.meeting_state

    async def get_presentation_state(self, session_id: str) -> PresentationMode:
        snap = await self.get_snapshot(session_id)
        return snap.presentation_state

    async def get_dom_summary(self, session_id: str) -> DOMSummary:
        snap = await self.get_snapshot(session_id)
        return snap.dom_summary

    def remove_history(self, session_id: str) -> None:
        """
        Disposes history context on session shutdown.
        """
        self._histories.pop(session_id, None)

semantic_browser_service = SemanticBrowserService()
