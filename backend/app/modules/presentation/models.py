from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class PresentationAction(BaseModel):
    action: str = Field(..., description="Action type: ADVANCE_SLIDE, REPEAT_SLIDE, WAIT, PAUSE, COMPLETE")
    reason: Optional[str] = None

class NarrationBlock(BaseModel):
    slide_number: int
    text: str
    estimated_duration: float
    emotion: str = "friendly_professional"
    pause_points: List[float] = []

class SlideData(BaseModel):
    slide_number: int
    title: str
    content: str
    speaker_notes: Optional[str] = None
    raw_narration: Optional[str] = None

class PresentationSession(BaseModel):
    session_id: str
    meeting_id: Optional[str] = None
    slides: List[SlideData] = []
    current_slide_index: int = 0
    total_slides: int = 0
    presentation_state: str = "WAITING"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

class PresentationStatusResponse(BaseModel):
    session_id: str
    presentation_state: str
    current_slide: int
    total_slides: int
    is_active: bool
    current_narration: Optional[str] = None
    last_action: Optional[str] = None
