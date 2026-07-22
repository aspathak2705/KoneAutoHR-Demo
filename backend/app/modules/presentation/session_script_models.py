from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CompletionRule(BaseModel):
    attendance_percent: Optional[float] = 80.0
    timeout_seconds: Optional[int] = 120

class FallbackRule(BaseModel):
    speak: Optional[str] = None
    periodic_speeches: List[str] = []

class CompleteWhenRule(BaseModel):
    responses: Optional[int] = None
    timeout: Optional[int] = 30
    speech_completed: Optional[bool] = True
    thumbs_up: Optional[bool] = None

class ScriptStep(BaseModel):
    step_id: int
    type: str = Field(..., description="Action type: WAIT_FOR_PARTICIPANTS, GREETING, INTRODUCTION, AUDIO_CHECK, SESSION_RULES, ICE_BREAKER, PRESENTATION_SECTION, SHOW_SLIDE, UNDERSTANDING_CHECK, SUMMARY, WAIT_FOR_QUESTIONS, CLOSING, LEAVE_MEETING, PLAY_VIDEO, SHOW_IMAGE, POLL, QUIZ, SCREEN_SHARE, OPEN_DOCUMENT, SURVEY")
    
    duration: Optional[int] = 60
    mandatory: Optional[bool] = True
    can_skip: Optional[bool] = False
    expected_response: Optional[str] = None
    completion: Optional[CompletionRule] = None
    fallback: Optional[FallbackRule] = None
    complete_when: Optional[CompleteWhenRule] = None
    
    speech: List[str] = []
    
    section_title: Optional[str] = None
    slides: List[int] = []
    learning_objective: Optional[str] = None
    transition: Optional[str] = None
    
    slide_id: Optional[str] = None
    slide_number: Optional[int] = None
    presentation_asset: Optional[str] = "presentation.json"
    speech_id: Optional[str] = None
    
    before: List[str] = []
    during: List[str] = []
    after: List[str] = []
    
    # Gap 7 Future Action Assets
    asset_url: Optional[str] = None
    poll_questions: List[Dict[str, Any]] = []
    quiz_items: List[Dict[str, Any]] = []
    
    extra_data: Optional[Dict[str, Any]] = None

class SessionScript(BaseModel):
    session_id: str
    company_name: str = "KONE"
    presenter_name: str = "KONE AutoHR Trainer"
    generated_at: str
    validated: bool = False
    validation_issues: List[str] = []
    steps: List[ScriptStep] = []

class SessionMemoryState(BaseModel):
    session_id: str
    current_step_index: int = 0
    total_steps: int = 0
    current_step_type: str = "IDLE"
    current_slide: int = 0
    participants_count: int = 0
    is_paused: bool = False
    completed_steps: List[int] = []

class SessionExecutionContext(BaseModel):
    session_id: str
    current_script_step: int
    completed_steps: List[int]
    pending_steps: List[int]
    current_runtime_state: str
    current_slide: int
    participants_count: int

# Gap 9 — Formalized Phase 2B.2 Contract
class QAContext(BaseModel):
    session_id: str
    memory: Dict[str, Any]
    attendance: Dict[str, Any]
    presentation_progress: Dict[str, Any]
    browser_session_active: bool
    knowledge_sources: Dict[str, Any]

# Session Validation Model
class ScriptValidationResult(BaseModel):
    is_valid: bool
    issues: List[str] = []
    checked_at: str
