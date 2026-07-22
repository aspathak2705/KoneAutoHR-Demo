from typing import List, Optional, Dict, Any
from app.schemas.common import BaseSchema

class SessionOpeningSchema(BaseSchema):
    greeting: str
    presenter_intro: str
    employee_welcome: str
    audio_check: str
    ice_breaker: str
    session_rules: str
    agenda: str

class SessionSlideSchema(BaseSchema):
    slide_number: int
    title: str
    objective: str
    transition_in: str
    narration: str
    understanding_check: str
    transition_out: str
    video_prompt: Optional[str] = None
    quiz_question: Optional[str] = None

class SessionClosingSchema(BaseSchema):
    summary: str
    next_steps: str
    farewell: str

class SessionScriptContentSchema(BaseSchema):
    opening: SessionOpeningSchema
    slides: List[SessionSlideSchema]
    closing: SessionClosingSchema
