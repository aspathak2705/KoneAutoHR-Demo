import re
import datetime
from sqlalchemy.orm import Session as DBSession
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.presentation import Presentation
from app.models.employee_list import EmployeeList
from app.models.presentation_script import PresentationScript
from app.models.presentation_question import PresentationQuestion
from app.models.organization_config import OrganizationConfig

class RuntimeValidationService:
    """
    Sprint RC-4 — Runtime Validation
    Ensures everything required for joining exists and has valid formats before launch.
    """
    def validate_runtime_readiness(self, db: DBSession, session_id: str) -> dict:
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        
        presentation = session.presentation
        if not presentation and session.presentation_id:
            presentation = db.query(Presentation).filter(Presentation.id == session.presentation_id).first()

        employee_list = session.employee_list
        if not employee_list and session.employee_list_id:
            employee_list = db.query(EmployeeList).filter(EmployeeList.id == session.employee_list_id).first()

        script = None
        questions = None
        if presentation:
            script = db.query(PresentationScript).filter(PresentationScript.presentation_id == presentation.id).first()
            questions = db.query(PresentationQuestion).filter(PresentationQuestion.presentation_id == presentation.id).first()

        config = db.query(OrganizationConfig).first()

        # Format Validations
        valid_url = False
        if meeting and meeting.teams_url:
            valid_url = bool(re.match(r"^https?://[^\s/$.?#].[^\s]*$", meeting.teams_url, re.IGNORECASE))

        valid_date = False
        if meeting and meeting.date:
            try:
                datetime.datetime.strptime(meeting.date, "%Y-%m-%d")
                valid_date = True
            except ValueError:
                valid_date = False

        valid_time = False
        if meeting and meeting.time:
            try:
                datetime.datetime.strptime(meeting.time, "%H:%M")
                valid_time = True
            except ValueError:
                valid_time = False

        # State Consistency
        state_consistent = session.status not in ["ARCHIVED", "DELETED"]

        checks = {
            "has_presentation": presentation is not None and bool(getattr(presentation, "original_filename", None) or getattr(presentation, "name", None)),
            "has_employees": employee_list is not None and getattr(employee_list, "employee_count", 0) > 0,
            "has_script": script is not None and bool(script.script_content),
            "has_faq": questions is not None and bool(questions.questions_content),
            "has_company_config": config is not None and bool(config.company_name),
            "valid_meeting_url_format": valid_url,
            "valid_meeting_date_format": valid_date,
            "valid_meeting_time_format": valid_time,
            "state_consistent": state_consistent,
            "has_presenter": meeting is not None and bool(meeting.organizer),
        }

        missing = [key for key, valid in checks.items() if not valid]
        is_ready = len(missing) == 0

        return {
            "session_id": session_id,
            "is_ready": is_ready,
            "checks": checks,
            "missing_components": missing
        }

    def assert_valid_for_launch(self, db: DBSession, session_id: str) -> None:
        """
        Fail fast assertion. Throws ValueError if required runtime assets or formats are invalid.
        """
        res = self.validate_runtime_readiness(db, session_id)
        if not res["is_ready"]:
            missing_str = ", ".join(res["missing_components"])
            raise ValueError(f"Runtime validation failed! Cannot launch meeting. Invalid or missing components: {missing_str}")

runtime_validation_service = RuntimeValidationService()
