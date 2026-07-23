from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.semantic_browser.models.semantic_state import DOMSummary, AccessibilitySummary

class SemanticSnapshot(BaseModel):
    timestamp: float
    meeting_state: MeetingState
    presentation_state: PresentationMode
    dom_summary: DOMSummary
    accessibility_summary: AccessibilitySummary
    chat_open: bool = False
    participants_open: bool = False
    recording_active: bool = False
    details: Dict[str, Any] = {}
