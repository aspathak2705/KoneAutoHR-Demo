import re
import datetime
from sqlalchemy.orm import Session as DBSession
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.presentation import Presentation
from app.models.employee import Employee
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
        presentation = db.query(Presentation).filter(Presentation.session_id == session_id).first()
        employees = db.query(Employee).filter(Employee.session_id == session_id).all()
        script = db.query(PresentationScript).filter(PresentationScript.session_id == session_id).first()
        questions = db.query(PresentationQuestion).filter(PresentationQuestion.session_id == session_id).first()
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
            "has_presentation": presentation is not None and bool(presentation.filename),
            "has_employees": len(employees) > 0,
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
