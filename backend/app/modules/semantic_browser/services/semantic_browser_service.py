from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.semantic_browser.browser.semantic_browser import semantic_browser
from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.semantic_browser.models.semantic_state import DOMSummary
from app.modules.semantic_browser.config import semantic_browser_config
from typing import List

class SemanticBrowserService:
    def __init__(self):
        self._history: List[SemanticSnapshot] = []

    async def get_snapshot(self) -> SemanticSnapshot:
        """
        Coordinates generating a complete current context SemanticSnapshot.
        Retains rolling history in memory.
        """
        bot = meeting_bot_service.get_bot()
        page = bot.context.page
        if not page:
            raise ValueError("SemanticBrowserService | Active browser page session not found.")
            
        snap = await semantic_browser.generate_snapshot(page)
        
        # Maintain in-memory history list
        self._history.append(snap)
        limit = semantic_browser_config.history_size
        if len(self._history) > limit:
            self._history = self._history[-limit:]
            
        return snap

    def get_history(self) -> List[SemanticSnapshot]:
        """
        Returns rolling history list of snapshots.
        """
        return self._history

    async def get_meeting_state(self) -> MeetingState:
        snap = await self.get_snapshot()
        return snap.meeting_state

    async def get_presentation_state(self) -> PresentationMode:
        snap = await self.get_snapshot()
        return snap.presentation_state

    async def get_dom_summary(self) -> DOMSummary:
        snap = await self.get_snapshot()
        return snap.dom_summary

semantic_browser_service = SemanticBrowserService()
