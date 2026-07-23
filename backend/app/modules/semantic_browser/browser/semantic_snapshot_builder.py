import time
from typing import Optional
from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.semantic_browser.models.semantic_state import DOMSummary, AccessibilitySummary

class SemanticSnapshotBuilder:
    @staticmethod
    def build(
        meeting_state: MeetingState,
        presentation_state: PresentationMode,
        dom_summary: DOMSummary,
        accessibility_summary: AccessibilitySummary,
        chat_open: bool,
        participants_open: bool,
        recording_active: bool,
        presentation_content_signature: Optional[str] = None,
        details: dict = None
    ) -> SemanticSnapshot:
        """
        Constructs a structured immutable SemanticSnapshot.
        """
        return SemanticSnapshot(
            timestamp=time.time(),
            meeting_state=meeting_state,
            presentation_state=presentation_state,
            dom_summary=dom_summary,
            accessibility_summary=accessibility_summary,
            chat_open=chat_open,
            participants_open=participants_open,
            recording_active=recording_active,
            presentation_content_signature=presentation_content_signature,
            details=details or {}
        )
