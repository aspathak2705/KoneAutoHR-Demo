from sqlalchemy.orm import Session as DBSession
from typing import Dict, Any, Optional
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.organization_config import OrganizationConfig
from app.repositories.presentation_script_repository import presentation_script_repository
from app.repositories.presentation_question_repository import presentation_question_repository
from app.modules.induction.employees.excel_parser import parse_employees_excel
from loguru import logger

class RuntimeService:
    def get_runtime_context(self, db: DBSession, session_id: str) -> Dict[str, Any]:
        """
        Sprint 2: Loads all prepared assets into memory and constructs
        the immutable AI Runtime Context. No LLM calls are made here.
        """
        # 1. Load Session
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError("Session not found.")

        # 2. Load Meeting Details
        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        if not meeting:
            raise ValueError("Teams meeting details not prepared for this session.")

        # 3. Load Presentation
        presentation = session.presentation
        if not presentation:
            raise ValueError("Presentation deck not loaded in this session.")

        # 4. Load Presentation Script
        script = presentation_script_repository.get_active(db, presentation.id)
        if not script or script.status != "COMPLETED":
            raise ValueError("AI presentation script has not been generated or is not ready.")

        # 5. Load FAQ / Questions
        faq = presentation_question_repository.get_active(db, presentation.id)
        if not faq or faq.status != "COMPLETED":
            raise ValueError("Expected employee FAQs have not been prepared.")

        # 6. Load Employees
        if not session.employee_list:
            raise ValueError("Employee register list not loaded in this session.")
        try:
            employees = parse_employees_excel(session.employee_list.storage_path)
        except Exception as e:
            raise ValueError(f"Failed to parse employees: {str(e)}")

        # 7. Load Company Persona / Organization Config
        persona = db.query(OrganizationConfig).first()
        if not persona:
            # Fallback default configuration
            persona = OrganizationConfig(
                company_name="KONE",
                company_domain="kone.com",
                ai_officer_name="KONE HR Officer",
                ai_trainer_name="KONE Trainer",
                ai_role_description="AI Onboarding Assistant",
                vocal_tone="Professional",
                communication_style="Direct"
            )

        # 8. Construct Immutable Runtime Context
        runtime_context = {
            "session_id": session_id,
            "session_name": session.name,
            "meeting": {
                "teams_meeting_url": meeting.teams_meeting_url,
                "meeting_passcode": meeting.meeting_passcode,
                "organizer_name": meeting.organizer_name,
                "meeting_date": meeting.meeting_date,
                "meeting_time": meeting.meeting_time
            },
            "presentation": {
                "id": presentation.id,
                "name": presentation.name,
                "original_filename": presentation.original_filename
            },
            "script": {
                "id": script.id,
                "welcome_flow": script.script_content.get("welcome_flow"),
                "slide_narrations": script.script_content.get("slide_narrations"),
                "closing_script": script.script_content.get("closing_script")
            },
            "faq": [
                {"question": q.get("question"), "answer": q.get("answer")}
                for q in faq.questions_content
            ],
            "employees": [
                {
                    "name": emp.get("name"),
                    "email": emp.get("email"),
                    "department": emp.get("department", "General"),
                    "role": emp.get("designation", "New Hire")
                }
                for emp in employees
            ],
            "persona": {
                "company_name": persona.company_name,
                "ai_trainer_name": persona.ai_trainer_name,
                "vocal_tone": persona.vocal_tone,
                "communication_style": persona.communication_style
            }
        }
        
        logger.info(f"RuntimeService | LoadContext | Session: {session_id} | Assets successfully loaded into memory.")
        return runtime_context

    def get_voice_config(self) -> Dict[str, Any]:
        """
        Sprint 2: Load TTS, STT, and voice configurations.
        """
        return {
            "tts_provider": "standard-azure-tts",
            "stt_provider": "whisper-v3",
            "voice_name": "en-US-JennyNeural",
            "speed": 1.0,
            "pitch": 1.0,
            "voice_gender": "Female"
        }

    def get_slide_controller(self, db: DBSession, session_id: str) -> Dict[str, Any]:
        """
        Sprint 2: Preload slide order, narrations, transitions, and video mappings.
        """
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session or not session.presentation_id:
            raise ValueError("Session or presentation not found.")
            
        script = presentation_script_repository.get_active(db, session.presentation_id)
        if not script:
            raise ValueError("Script not found.")

        slide_narrations = script.script_content.get("slide_narrations", {})
        slide_order = sorted([int(k) for k in slide_narrations.keys()])
        
        slides = []
        for slide_num in slide_order:
            item = slide_narrations.get(str(slide_num), {})
            slides.append({
                "slide_number": slide_num,
                "learning_objective": item.get("learning_objective", ""),
                "narration": item.get("narration", ""),
                "transition": "crossfade",
                "embedded_video": None
            })

        return {
            "total_slides": len(slides),
            "slides": slides,
            "loop_presentation": False
        }

runtime_service = RuntimeService()
