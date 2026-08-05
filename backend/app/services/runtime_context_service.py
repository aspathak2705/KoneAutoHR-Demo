from sqlalchemy.orm import Session as DBSession
from typing import Dict, Any, Optional

from app.models.session import Session
from app.models.presentation import Presentation
from app.models.employee_list import EmployeeList
from app.models.presentation_script import PresentationScript
from app.models.presentation_question import PresentationQuestion
from app.models.meeting import Meeting
from app.models.organization_config import OrganizationConfig

class RuntimeContextService:
    """
    Phase 2 — Runtime Context Builder
    Assembles all runtime dependencies (Presentation Asset, Script, Questions, Employee List, Meeting, Config)
    for a given session without performing validation or raising readiness exceptions.
    """

    def build_runtime_context(self, db: DBSession, session_id: str) -> Dict[str, Any]:
        """
        Resolves asset references:
        Session -> Presentation Asset -> Presentation Script & Questions
        Session -> Employee List Asset
        Session -> Meeting & Organization Config
        """
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            return {
                "session_id": session_id,
                "session_exists": False,
                "presentation_asset": None,
                "presentation_script": None,
                "presentation_questions": None,
                "employee_list_asset": None,
                "meeting": None,
                "organization_config": None
            }

        # Resolve Presentation Asset & Linked Script/Questions (Phase 7 Asset Resolution Policy)
        presentation_asset = None
        presentation_script = None
        presentation_questions = None

        if session.presentation_id:
            presentation_asset = db.query(Presentation).filter(Presentation.id == session.presentation_id).first()
            if presentation_asset:
                presentation_script = db.query(PresentationScript).filter(
                    PresentationScript.presentation_id == presentation_asset.id
                ).first()
                presentation_questions = db.query(PresentationQuestion).filter(
                    PresentationQuestion.presentation_id == presentation_asset.id
                ).first()

        # Resolve Employee List Asset
        employee_list_asset = None
        if session.employee_list_id:
            employee_list_asset = db.query(EmployeeList).filter(EmployeeList.id == session.employee_list_id).first()

        # Resolve Meeting & Organization Config
        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        organization_config = db.query(OrganizationConfig).first()

        return {
            "session_id": session_id,
            "session_exists": True,
            "session": session,
            "creation_mode": getattr(session, "creation_mode", "AI") or "AI",
            "presentation_asset": presentation_asset,
            "presentation_script": presentation_script,
            "presentation_questions": presentation_questions,
            "employee_list_asset": employee_list_asset,
            "meeting": meeting,
            "organization_config": organization_config
        }

runtime_context_service = RuntimeContextService()
