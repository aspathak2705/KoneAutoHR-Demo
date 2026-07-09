from pydantic import BaseModel
from typing import List, Dict, Optional

class SessionMetadataSchema(BaseModel):
    session_id: str
    name: str
    company_name: str
    department: Optional[str] = None
    scheduled_at: Optional[str] = None
    language: str
    session_type: str

class EmployeeProfileSchema(BaseModel):
    name: str
    email: str
    department: str
    designation: str
    location: Optional[str] = None

class AudienceSummarySchema(BaseModel):
    total_employees: int
    audience_type: str
    departments_represented: List[str]
    new_hires_count: int
    technical_level: str

class WelcomeFlowSchema(BaseModel):
    greeting: str
    wait_message: str
    audio_check: str
    ice_breaker: str
    agenda: List[str]

class SlideKnowledgeSchema(BaseModel):
    slide_number: int
    title: str
    content: str
    speaker_notes: Optional[str] = None
    images: List[str]
    videos: List[str]

class SlideNarrationSchema(BaseModel):
    slide_number: int
    narration: str
    transition: Optional[str] = None
    interactive_prompt: Optional[str] = None
    expected_questions: List[Dict[str, str]]

class ClosingScriptSchema(BaseModel):
    summary: str
    congratulations: str
    next_steps: str

class SessionStateSchema(BaseModel):
    current_slide: int = 1
    status: str = "prepared"
    progress: float = 0.0

class InductionPackage(BaseModel):
    session_metadata: SessionMetadataSchema
    meeting_context: Dict[str, str]
    employee_profiles: List[EmployeeProfileSchema]
    audience_summary: AudienceSummarySchema
    welcome_flow: WelcomeFlowSchema
    slide_knowledge: List[SlideKnowledgeSchema]
    slide_narrations: Dict[str, SlideNarrationSchema]
    closing_script: ClosingScriptSchema
    session_state: SessionStateSchema
