from sqlalchemy.orm import Session as DBSession
from typing import List, Optional, Dict, Any
import datetime
from pathlib import Path

from app.models.session import Session
from app.models.presentation import Presentation
from app.models.employee_list import EmployeeList
from app.models.presentation_script import PresentationScript
from app.models.presentation_question import PresentationQuestion
from app.models.meeting import Meeting

from app.repositories.session_repository import session_repository
from app.repositories.presentation_repository import presentation_repository
from app.repositories.employee_list_repository import employee_list_repository
from app.repositories.presentation_script_repository import presentation_script_repository
from app.repositories.presentation_question_repository import presentation_question_repository

class AssetService:
    """
    Phase J — Asset Manager & Reusable Asset Library Service
    Manages long-lived organizational assets (Presentations, Employee Lists, Scripts, FAQs)
    and handles asset linking & reuse across induction sessions.
    """

    def list_presentation_assets(self, db: DBSession) -> List[Dict[str, Any]]:
        """
        Phase G — Returns available presentation assets from Asset Library.
        """
        presentations = db.query(Presentation).order_by(Presentation.last_used.desc()).all()
        result = []
        for pres in presentations:
            script = db.query(PresentationScript).filter(PresentationScript.presentation_id == pres.id).first()
            faq = db.query(PresentationQuestion).filter(PresentationQuestion.presentation_id == pres.id).first()
            result.append({
                "id": pres.id,
                "name": pres.name,
                "original_filename": pres.original_filename,
                "storage_path": pres.storage_path,
                "uploaded_at": pres.uploaded_at.isoformat() if pres.uploaded_at else None,
                "last_used": pres.last_used.isoformat() if pres.last_used else None,
                "session_count": pres.session_count,
                "has_script": script is not None and bool(script.script_content),
                "has_faq": faq is not None and bool(faq.questions_content)
            })
        return result

    def list_employee_list_assets(self, db: DBSession) -> List[Dict[str, Any]]:
        """
        Phase G — Returns available employee list assets from Asset Library.
        """
        employee_lists = db.query(EmployeeList).order_by(EmployeeList.last_used.desc()).all()
        result = []
        for emp_list in employee_lists:
            result.append({
                "id": emp_list.id,
                "name": emp_list.name,
                "original_filename": emp_list.original_filename,
                "storage_path": emp_list.storage_path,
                "uploaded_at": emp_list.uploaded_at.isoformat() if emp_list.uploaded_at else None,
                "last_used": emp_list.last_heartbeat.isoformat() if hasattr(emp_list, "last_heartbeat") and emp_list.last_heartbeat else (emp_list.last_used.isoformat() if emp_list.last_used else None),
                "employee_count": emp_list.employee_count
            })
        return result

    def link_assets_to_session(
        self,
        db: DBSession,
        session_id: str,
        presentation_id: Optional[str] = None,
        employee_list_id: Optional[str] = None
    ) -> Session:
        """
        Phase B & C — Links presentation asset or employee list asset to session.
        Phase D — Automatically reuses AI script & questions if already generated for presentation asset.
        """
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        if presentation_id:
            pres = db.query(Presentation).filter(Presentation.id == presentation_id).first()
            if not pres:
                raise ValueError(f"Presentation asset {presentation_id} not found.")
            session.presentation_id = presentation_id
            pres.last_used = datetime.datetime.now()
            pres.session_count += 1

        if employee_list_id:
            emp = db.query(EmployeeList).filter(EmployeeList.id == employee_list_id).first()
            if not emp:
                raise ValueError(f"Employee list asset {employee_list_id} not found.")
            session.employee_list_id = employee_list_id
            emp.last_used = datetime.datetime.now()

        db.commit()
        db.refresh(session)
        return session

    def validate_linked_assets_readiness(self, db: DBSession, session_id: str) -> dict:
        """
        Phase E & H & I — Validates linked presentation, employee list, script, questions, and meeting configuration.
        """
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        has_presentation = session.presentation_id is not None
        has_employees = session.employee_list_id is not None

        script = None
        questions = None
        if has_presentation:
            script = presentation_script_repository.get_active(db, session.presentation_id)
            questions = presentation_question_repository.get_active(db, session.presentation_id)

        is_hr_mode = getattr(session, "creation_mode", "AI") == "HR"
        has_script = True if is_hr_mode else (script is not None and bool(script.script_content))
        has_faq = True if is_hr_mode else (questions is not None and bool(questions.questions_content))

        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        has_meeting = meeting is not None and bool(meeting.teams_url) and bool(meeting.date) and bool(meeting.time)

        is_ready = has_presentation and has_employees and has_script and has_faq and has_meeting

        return {
            "session_id": session_id,
            "has_presentation": has_presentation,
            "has_employees": has_employees,
            "has_script": has_script,
            "has_faq": has_faq,
            "has_meeting": has_meeting,
            "is_ready": is_ready
        }

asset_service = AssetService()
