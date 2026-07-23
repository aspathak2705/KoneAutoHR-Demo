import datetime
from sqlalchemy.orm import Session as DBSession
from app.modules.configuration.configuration_service import configuration_service
from app.modules.induction.context.meeting_context import build_meeting_context
from app.modules.induction.employees.profiler import profile_employees
from app.modules.induction.employees.audience_builder import build_audience_summary

class ContextBuilder:
    def build_context(
        self,
        db: DBSession,
        session,
        slide_knowledge: list,
        employee_rows: list
    ) -> dict:
        """
        Gathers and aggregates all parsed inputs, configs, profiles and policies into a single structured context.
        """
        meeting_ctx = build_meeting_context(session)
        config = configuration_service.get_active_config(db)
        
        employee_profiles = profile_employees(employee_rows)
        audience_summary = build_audience_summary(employee_profiles)

        # 1. Structure presenter profile
        presenter_profile = {
            "company_name": meeting_ctx["company_name"],
            "company_domain": meeting_ctx["company_domain"],
            "ai_officer_name": meeting_ctx["ai_officer_name"],
            "ai_trainer_name": meeting_ctx["ai_trainer_name"],
            "ai_role_description": meeting_ctx["ai_role_description"],
            "vocal_tone": meeting_ctx["vocal_tone"],
            "communication_style": meeting_ctx["communication_style"]
        }

        # 2. Compile Agenda & Policies
        agenda = [s["title"] for s in slide_knowledge]
        policies = {
            "session_rules": [
                "Keep microphones muted unless speaking.",
                "Questions can be typed in the chat window anytime.",
                "Active participation in checkpoints is encouraged."
            ],
            "security_policy": f"This induction and the shared slide deck are proprietary to {meeting_ctx['company_name']}."
        }

        # 3. Assemble complete structured context
        structured_context = {
            "session": {
                "id": session.id,
                "name": session.name,
                "presentation_id": session.presentation_id,
                "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None,
                "department": meeting_ctx["department"],
                "language": meeting_ctx["language"],
                "session_type": meeting_ctx["session_type"]
            },
            "presenter_profile": presenter_profile,
            "audience": {
                "total_invited": len(employee_profiles),
                "summary": audience_summary,
                "profiles": employee_profiles
            },
            "presentation": {
                "slides": slide_knowledge,
                "total_slides": len(slide_knowledge),
                "agenda": agenda
            },
            "policies": policies,
            "runtime_config": {
                "default_pause_seconds": 1.5,
                "interactive_qa_enabled": True,
                "recording_enabled": False
            }
        }

        return structured_context

context_builder = ContextBuilder()
