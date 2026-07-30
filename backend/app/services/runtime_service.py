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
    def __init__(self):
        self._coordinators = {}

    def create_runtime_and_coordinator(self, db: DBSession, session_id: str):
        """
        Creates a new Runtime entry and initializes RuntimeCoordinator.
        Returns the coordinator in NOT_CREATED state, ready for prepare_runtime().
        """
        from app.modules.induction_runtime.orchestrator.runtime_coordinator import RuntimeCoordinator
        from app.models.runtime import Runtime
        import uuid
        
        logger.info(f"RuntimeService | START create_runtime_and_coordinator for session {session_id}")
        
        try:
            # Create Runtime database entry
            runtime_id = str(uuid.uuid4())
            runtime = Runtime(
                id=runtime_id,
                session_id=session_id,
                state="NOT_CREATED"
            )
            db.add(runtime)
            db.commit()
            logger.info(f"RuntimeService | Created Runtime entry: {runtime_id}")
            
            # Create coordinator with runtime_id
            coordinator = RuntimeCoordinator(db, session_id, runtime_id=runtime_id)
            self._coordinators[session_id] = coordinator
            
            logger.info(f"RuntimeService | SUCCESS created coordinator for session {session_id}")
            return coordinator
        except Exception as e:
            logger.error(f"RuntimeService | FAILED create_runtime_and_coordinator: {e}")
            raise

    def get_coordinator(self, db: DBSession, session_id: str):
        """
        Retrieves cached coordinator.
        """
        if session_id not in self._coordinators:
            logger.info(f"RuntimeService | Coordinator not cached for {session_id}")
            raise ValueError("Runtime not prepared")
        return self._coordinators[session_id]

    def remove_coordinator(self, session_id: str) -> None:
        """
        Removes coordinator from cache when session completes.
        """
        self._coordinators.pop(session_id, None)
        logger.info(f"RuntimeService | Removed coordinator from cache for session {session_id}")

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
        if not script or script.status not in ["ACTIVE", "COMPLETED"]:
            raise ValueError("AI presentation script has not been generated or is not ready.")

        script_payload = script.script_content
        if isinstance(script_payload, str):
            try:
                import json
                script_payload = json.loads(script_payload)
            except Exception:
                script_payload = {}
        elif not isinstance(script_payload, dict):
            script_payload = {}

        # 5. Load FAQ / Questions
        faq = presentation_question_repository.get_active(db, presentation.id)
        if not faq or faq.status not in ["ACTIVE", "COMPLETED"]:
            raise ValueError("Expected employee FAQs have not been prepared.")

        faq_payload = faq.questions_content
        if isinstance(faq_payload, str):
            try:
                import json
                faq_payload = json.loads(faq_payload)
            except Exception:
                faq_payload = []
        elif not isinstance(faq_payload, list):
            faq_payload = []

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
                "welcome_flow": script_payload.get("welcome_flow") if isinstance(script_payload, dict) else {},
                "slide_narrations": script_payload.get("slide_narrations") if isinstance(script_payload, dict) else {},
                "closing_script": script_payload.get("closing_script") if isinstance(script_payload, dict) else ""
            },
            "faq": [
                {"question": q.get("question"), "answer": q.get("answer")}
                for q in faq_payload if isinstance(q, dict)
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

        script_payload = script.script_content
        if isinstance(script_payload, str):
            try:
                import json
                script_payload = json.loads(script_payload)
            except Exception:
                script_payload = {}
        elif not isinstance(script_payload, dict):
            script_payload = {}

        slide_narrations = script_payload.get("slide_narrations", {}) if isinstance(script_payload, dict) else {}
        slides = []
        
        if "slides" in script_payload and isinstance(script_payload["slides"], list):
            for s in script_payload["slides"]:
                slide_num = int(s.get("slide_number", 1))
                slides.append({
                    "slide_number": slide_num,
                    "learning_objective": s.get("objective", ""),
                    "narration": s.get("narration", ""),
                    "transition": s.get("transition_in", "crossfade"),
                    "embedded_video": None
                })
        else:
            slide_order = sorted([int(k) for k in slide_narrations.keys()])
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
