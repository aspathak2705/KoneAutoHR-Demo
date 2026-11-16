import os
from pathlib import Path
from sqlalchemy.orm import Session as DBSession
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.runtime import Runtime
from app.models.runtime_message import RuntimeMessage
from app.models.organization_config import OrganizationConfig
from app.models.attendance import Attendance
from app.services.storage_service import storage_service
from app.modules.induction.employees.excel_parser import parse_employees_excel
from loguru import logger

class ReportService:
    def compile_session_report(self, db: DBSession, session_id: str) -> dict:
        """
        Sprint 5 / Remediation: Compiles summary report details from session run context.
        Uses actual verified attendance records when captured. If no verified participant
        signals were captured, marks attendance as Unverified and does not fabricate attendance.
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

        # Query actual persisted attendance logs for this session
        attendance_logs = db.query(Attendance).filter(Attendance.session_id == session_id).all()
        log_by_email = {log.attendee_email.lower().strip(): log for log in attendance_logs if log.attendee_email}
        log_by_name = {log.attendee_name.lower().strip(): log for log in attendance_logs if log.attendee_name}

        # Parse employee list for roster
        employees = []
        matched_log_ids = set()
        if session.employee_list:
            try:
                from app.core.security.secure_storage import secure_storage
                with secure_storage.open_decrypted_file(session.employee_list) as decrypted_emp_path:
                    emp_list = parse_employees_excel(str(decrypted_emp_path))
                
                has_real_attendance = len(attendance_logs) > 0

                for emp in emp_list:
                    emp_name = emp.get("name") or "Unknown"
                    emp_email = (emp.get("email") or "").lower().strip()
                    
                    matched_log = None
                    if emp_email and emp_email in log_by_email:
                        matched_log = log_by_email[emp_email]
                    elif emp_name.lower().strip() in log_by_name:
                        matched_log = log_by_name[emp_name.lower().strip()]

                    if matched_log:
                        matched_log_ids.add(matched_log.id)
                        status = matched_log.status or "Attended"
                        join_time = matched_log.joined_at.isoformat() if matched_log.joined_at else None
                        duration = round(matched_log.duration_seconds / 60, 1) if matched_log.duration_seconds else None
                    elif has_real_attendance:
                        status = "Absent"
                        join_time = None
                        duration = None
                    else:
                        status = "Unverified (No participant signals captured)"
                        join_time = None
                        duration = None

                    employees.append({
                        "name": emp_name,
                        "email": emp.get("email"),
                        "department": emp.get("department", "General"),
                        "role": emp.get("designation", "New Hire"),
                        "status": status,
                        "joined_at": join_time,
                        "duration_minutes": duration
                    })
            except Exception as e:
                logger.error(f"ReportService | Error parsing employee list: {e}")
        elif attendance_logs:
            # Session had no uploaded employee list, but attendance logs were captured directly from call
            for log in attendance_logs:
                matched_log_ids.add(log.id)
                employees.append({
                    "name": log.attendee_name,
                    "email": log.attendee_email,
                    "department": "Participant",
                    "role": "Attendee",
                    "status": log.status or "Attended",
                    "joined_at": log.joined_at.isoformat() if log.joined_at else None,
                    "duration_minutes": round(log.duration_seconds / 60, 1) if log.duration_seconds else None
                })

        # Append any un-rostered participants who joined the meeting
        for log in attendance_logs:
            if log.id not in matched_log_ids:
                employees.append({
                    "name": log.attendee_name,
                    "email": log.attendee_email,
                    "department": "Unmatched Participant",
                    "role": "Guest",
                    "status": log.status or "Attended",
                    "joined_at": log.joined_at.isoformat() if log.joined_at else None,
                    "duration_minutes": round(log.duration_seconds / 60, 1) if log.duration_seconds else None
                })

        # Compute attendance metrics based strictly on evidence
        total_invited = len(employees)
        verified_attended = len([e for e in employees if e["status"] in ("PRESENT", "Attended", "PARTIAL")])
        verified_absent = len([e for e in employees if e["status"] == "Absent"])
        unverified_count = len([e for e in employees if "Unverified" in e["status"]])

        has_verified_data = total_invited > 0 and unverified_count == 0
        participation_rate = round((verified_attended / total_invited * 100), 1) if has_verified_data else None

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
                "invited": total_invited,
                "verified_attended": verified_attended,
                "verified_absent": verified_absent,
                "unverified": unverified_count,
                "has_verified_data": has_verified_data,
                "participation_rate": f"{participation_rate}%" if participation_rate is not None else "Not Available (Unverified)",
                "verification_status": "Verified via Live Participant Logs" if has_verified_data else "Not Available (Participant telemetry was not captured)",
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
- **Attendance Verification:** {report_data['attendance']['verification_status']}
- **Total Invited:** {report_data['attendance']['invited']}
- **Verified Attended:** {report_data['attendance']['verified_attended']}
- **Verified Absent:** {report_data['attendance']['verified_absent']}
- **Unverified Status:** {report_data['attendance']['unverified']}
- **Participation Rate:** {report_data['attendance']['participation_rate']}

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
