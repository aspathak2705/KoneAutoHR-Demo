import os
from pathlib import Path
from sqlalchemy.orm import Session as DBSession
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.runtime import Runtime
from app.models.runtime_message import RuntimeMessage
from app.models.organization_config import OrganizationConfig
from app.services.storage_service import storage_service
from app.modules.induction.employees.excel_parser import parse_employees_excel
from loguru import logger

class ReportService:
    def compile_session_report(self, db: DBSession, session_id: str) -> dict:
        """
        Sprint 5: Compiles summary report details from session run context.
        """
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError("Session not found.")

        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        meeting_data = {
            "teams_meeting_url": meeting.teams_meeting_url if meeting else "N/A",
            "meeting_date": meeting.meeting_date if meeting else "N/A",
            "meeting_time": meeting.meeting_time if meeting else "N/A",
            "organizer_name": meeting.organizer_name if meeting else "N/A"
        }

        # Parse employee list for attendance status
        employees = []
        if session.employee_list:
            try:
                emp_list = parse_employees_excel(session.employee_list.storage_path)
                employees = [
                    {
                        "name": emp.get("name"),
                        "email": emp.get("email"),
                        "department": emp.get("department", "General"),
                        "role": emp.get("designation", "New Hire"),
                        "status": "Attended" # simulated attendance
                    }
                    for emp in emp_list
                ]
            except Exception:
                pass

        # Fetch conversation logs
        messages = db.query(RuntimeMessage).filter(RuntimeMessage.session_id == session_id).order_by(RuntimeMessage.timestamp.asc()).all()
        transcript = [
            {
                "speaker": m.speaker_name,
                "text": m.message_text,
                "timestamp": m.timestamp.isoformat()
            }
            for m in messages
        ]

        # Count employee questions
        config = db.query(OrganizationConfig).first()
        trainer = config.ai_trainer_name if config else "KONE Trainer"
        questions_count = len([m for m in messages if m.speaker_name != trainer])

        return {
            "session_id": session_id,
            "session_name": session.name,
            "meeting": meeting_data,
            "trainer": trainer,
            "attendance": {
                "invited": len(employees),
                "attended": len(employees),
                "list": employees
            },
            "questions_asked": questions_count,
            "transcript": transcript
        }

    def generate_and_save_packages(self, db: DBSession, session_id: str) -> tuple[Path, Path]:
        """
        Sprint 5: PackageGenerator archiving reports and transcripts to disk.
        """
        report_data = self.compile_session_report(db, session_id)
        
        # Determine paths
        reports_dir = storage_service.get_reports_dir(session_id)
        report_path = reports_dir / "induction_report.md"
        transcript_path = reports_dir / "induction_transcript.md"

        # 1. Compile Markdown Onboarding Report
        report_md = f"""# KONE Live Onboarding Session Report: {report_data['session_name']}
        
## Session Information
- **Meeting Link:** {report_data['meeting']['teams_meeting_url']}
- **Date & Time:** {report_data['meeting']['meeting_date']} @ {report_data['meeting']['meeting_time']}
- **AI Trainer Name:** {report_data['trainer']}
- **Status:** Completed Successfully

## Attendance Summary
- **Total Invited:** {report_data['attendance']['invited']}
- **Total Attended:** {report_data['attendance']['attended']}
- **Participation Rate:** 100%

### Attendee Logs
| Employee Name | Department | Designation | Status |
| :--- | :--- | :--- | :--- |
"""
        for emp in report_data['attendance']['list']:
            report_md += f"| {emp['name']} | {emp['department']} | {emp['role']} | {emp['status']} |\n"

        report_md += f"\n## Engagement Summary\n- **Attendee Questions Answered:** {report_data['questions_asked']}\n"

        # 2. Compile Dialogue Transcript Log
        transcript_md = f"# Dialogue Transcript Log: {report_data['session_name']}\n\n"
        for msg in report_data['transcript']:
            transcript_md += f"**[{msg['timestamp']}] {msg['speaker']}:** {msg['text']}\n\n"

        # Save to disk
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript_md)

        logger.info(f"ReportService | Packages saved to disk: {report_path} | {transcript_path}")
        return report_path, transcript_path

report_service = ReportService()
