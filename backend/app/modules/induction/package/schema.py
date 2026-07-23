from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class SessionMetadataSchema(BaseModel):
    session_id: str
    name: str
    company_name: str
    department: Optional[str] = None
    scheduled_at: Optional[str] = None
    language: str
    session_type: str
    meeting_duration: int = 60
    timezone: str = "UTC"
    company_domain: str = "kone.com"
    prepared_at: str
    prepared_by_version: str = "1.0.0"

class AIPersonaSchema(BaseModel):
    name: str = "KONE AI Induction Officer"
    role: str = "HR Induction Officer"
    tone: str = "Professional, Friendly"
    communication_style: str = "Conversational"
    company: str = "KONE"

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
    meeting_join_message: str
    participant_wait_timeout: int = 60
    late_joiner_message: str
    start_confirmation: str

class SlideKnowledgeSchema(BaseModel):
    slide_number: int
    title: str
    content: str
    speaker_notes: Optional[str] = None
    images: List[str]
    videos: List[str]

class VideoScriptSchema(BaseModel):
    before_video: str
    after_video: str
    pause_after_video: bool = True
    resume_message: str

class SlideNarrationSchema(BaseModel):
    slide_number: int
    narration: str
    transition: Optional[str] = None
    interactive_prompt: Optional[str] = None
    learning_objective: str
    key_takeaways: List[str]
    story_example: Optional[str] = None
    video_script: Optional[VideoScriptSchema] = None

class FAQItemSchema(BaseModel):
    question: str
    answer: str
    confidence: float = 1.0
    references: List[int]

class ClosingScriptSchema(BaseModel):
    summary: str
    congratulations: str
    next_steps: str

class SessionStateSchema(BaseModel):
    current_slide: int = 1
    status: str = "prepared"
    progress: float = 0.0

class InductionPackage(BaseModel):
    schema_version: str = "1.0"
    package_version: str = "1.0"
    session_metadata: SessionMetadataSchema
    meeting_context: Dict[str, str]
    ai_persona: AIPersonaSchema
    employee_profiles: List[EmployeeProfileSchema]
    audience_summary: AudienceSummarySchema
    welcome_flow: WelcomeFlowSchema
    slide_knowledge: List[SlideKnowledgeSchema]
    slide_narrations: Dict[str, SlideNarrationSchema]
    faq: List[FAQItemSchema]
    closing_script: ClosingScriptSchema
    session_state: SessionStateSchema
    audio_metadata: Optional[List[Dict[str, Any]]] = None

class PackageManifest(BaseModel):
    package_version: str = "1.0.0"
    creation_time: str
    session_id: str
    presentation_version: int = 1
    session_script: str = "session_script.json"
    runtime_metadata: str = "runtime_metadata.json"
    audio_manifest: str = "audio_manifest.json"
    validation_report: str = "validation_report.json"
    assets: List[Dict[str, Any]] = []
    checksums: Dict[str, str] = {}
    generation_status: str = "READY"
    runtime_version: str = "0.1.0"

class RuntimeMetadataEntry(BaseModel):
    slide_id: str
    audio_file: Optional[str] = None
    duration: float
    start_delay: float = 0.0
    expected_slide: int
    contains_video: bool = False
    pause_points: List[float] = []
    hash: str = ""
    version: int = 1
    language: str = "English"
    voice: str
    generation_time: str

class PresentationPackage(BaseModel):
    manifest: PackageManifest
    session_script: Dict[str, Any]
    audio_manifest: Dict[str, Any]
    runtime_metadata: List[RuntimeMetadataEntry]
    validation_report: Dict[str, Any]
    assets_dir: str
