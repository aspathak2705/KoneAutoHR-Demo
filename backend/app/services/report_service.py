import os
import io
import zipfile
import xml.sax.saxutils as saxutils
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
        
        # Build name-to-logs index to detect duplicate names
        name_to_logs = {}
        for log in attendance_logs:
            if log.attendee_name:
                key = log.attendee_name.lower().strip()
                name_to_logs.setdefault(key, []).append(log)

        # Parse employee list for roster
        employees = []
        matched_log_ids = set()
        if session.employee_list:
            try:
                from app.core.security.secure_storage import secure_storage
                with secure_storage.open_decrypted_file(session.employee_list) as decrypted_emp_path:
                    emp_list = parse_employees_excel(str(decrypted_emp_path))
                
                # Count name occurrences in roster to prevent ambiguous matches
                roster_name_counts = {}
                for e in emp_list:
                    nm = (e.get("name") or "").lower().strip()
                    if nm:
                        roster_name_counts[nm] = roster_name_counts.get(nm, 0) + 1

                has_real_attendance = len(attendance_logs) > 0

                for emp in emp_list:
                    emp_name = emp.get("name") or "Unknown"
                    emp_email = (emp.get("email") or "").lower().strip()
                    norm_name = emp_name.lower().strip()
                    
                    matched_log = None
                    # Priority 1: Match by authoritative unique identifier (email)
                    if emp_email and emp_email in log_by_email:
                        matched_log = log_by_email[emp_email]
                    # Priority 2: Match by name ONLY if name is strictly unique in both roster and captured logs
                    elif (
                        norm_name in name_to_logs
                        and len(name_to_logs[norm_name]) == 1
                        and roster_name_counts.get(norm_name, 0) == 1
                        and name_to_logs[norm_name][0].id not in matched_log_ids
                    ):
                        matched_log = name_to_logs[norm_name][0]

                    if matched_log:
                        matched_log_ids.add(matched_log.id)
                        status = matched_log.status or "Attended"
                        join_time = matched_log.joined_at.isoformat() if matched_log.joined_at else None
                        duration = round(matched_log.duration_seconds / 60, 1) if matched_log.duration_seconds else None
                    elif has_real_attendance:
                        # If the name is ambiguous (appears multiple times), mark as requiring review
                        if norm_name in name_to_logs and (len(name_to_logs[norm_name]) > 1 or roster_name_counts.get(norm_name, 0) > 1):
                            status = "Unverified (Ambiguous name match - review required)"
                        else:
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

        # Generate PDF & DOCX packages
        pdf_path = reports_dir / "induction_report.pdf"
        docx_path = reports_dir / "induction_report.docx"
        try:
            self.generate_pdf_file(report_data, pdf_path)
            self.generate_docx_file(report_data, docx_path)
        except Exception as e:
            logger.warning(f"ReportService | Additional export generation error (non-fatal): {e}")

        logger.info(f"ReportService | Packages saved to disk: {report_path} | {transcript_path}")
        return report_path, transcript_path

    def generate_pdf_file(self, report_data: dict, output_path: Path) -> Path:
        """
        Generates professional styled KONE corporate onboarding PDF report using ReportLab.
        """
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        styles = getSampleStyleSheet()

        kone_blue = colors.HexColor("#0057B8")
        dark_text = colors.HexColor("#1E293B")
        muted_text = colors.HexColor("#64748B")
        light_bg = colors.HexColor("#F8FAFC")
        border_color = colors.HexColor("#CBD5E1")

        title_style = ParagraphStyle(
            "KoneTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=kone_blue,
            fontName="Helvetica-Bold",
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            "KoneSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=muted_text,
            spaceAfter=12
        )
        h2_style = ParagraphStyle(
            "KoneH2",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=kone_blue,
            fontName="Helvetica-Bold",
            spaceBefore=10,
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            "KoneBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=dark_text
        )
        th_style = ParagraphStyle(
            "KoneTH",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            fontName="Helvetica-Bold",
            textColor=colors.white
        )

        elements = []

        # Header Title
        elements.append(Paragraph("KONE AutoHR — Live Onboarding Session Report", title_style))
        elements.append(Paragraph(f"Session: {saxutils.escape(report_data.get('session_name', ''))}", subtitle_style))
        elements.append(Spacer(1, 4))

        # Session Information Table
        meeting = report_data.get("meeting", {})
        info_data = [
            [Paragraph("<b>Meeting Date & Time:</b>", body_style), Paragraph(f"{meeting.get('meeting_date', 'N/A')} @ {meeting.get('meeting_time', 'N/A')}", body_style)],
            [Paragraph("<b>Teams URL:</b>", body_style), Paragraph(meeting.get("teams_meeting_url", "N/A"), body_style)],
            [Paragraph("<b>AI / Host Trainer:</b>", body_style), Paragraph(report_data.get("trainer", "KONE Trainer"), body_style)],
            [Paragraph("<b>Attendance Verification:</b>", body_style), Paragraph(report_data.get("attendance", {}).get("verification_status", "N/A"), body_style)],
        ]
        info_table = Table(info_data, colWidths=[150, 390])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), light_bg),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 10))

        # Attendance Metrics Summary Table
        att = report_data.get("attendance", {})
        elements.append(Paragraph("Attendance Metrics", h2_style))
        metrics_data = [
            [
                Paragraph("<b>Total Invited</b>", body_style),
                Paragraph("<b>Verified Attended</b>", body_style),
                Paragraph("<b>Verified Absent</b>", body_style),
                Paragraph("<b>Unverified</b>", body_style),
                Paragraph("<b>Participation Rate</b>", body_style),
            ],
            [
                Paragraph(str(att.get("invited", 0)), body_style),
                Paragraph(str(att.get("verified_attended", 0)), body_style),
                Paragraph(str(att.get("verified_absent", 0)), body_style),
                Paragraph(str(att.get("unverified", 0)), body_style),
                Paragraph(str(att.get("participation_rate", "N/A")), body_style),
            ]
        ]
        metrics_table = Table(metrics_data, colWidths=[108, 108, 108, 108, 108])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 10))

        # Attendee List Table
        elements.append(Paragraph("Attendee Roster", h2_style))
        emp_rows = [
            [
                Paragraph("Employee Name", th_style),
                Paragraph("Department", th_style),
                Paragraph("Designation", th_style),
                Paragraph("Attendance Status", th_style),
            ]
        ]
        for emp in att.get("list", []):
            status_text = emp.get("status", "Absent")
            emp_rows.append([
                Paragraph(saxutils.escape(emp.get("name", "")), body_style),
                Paragraph(saxutils.escape(emp.get("department", "")), body_style),
                Paragraph(saxutils.escape(emp.get("role", "")), body_style),
                Paragraph(saxutils.escape(status_text), body_style),
            ])

        if len(emp_rows) == 1:
            emp_rows.append([Paragraph("No attendees registered.", body_style), Paragraph("", body_style), Paragraph("", body_style), Paragraph("", body_style)])

        emp_table = Table(emp_rows, colWidths=[150, 130, 130, 130])
        emp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), kone_blue),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_bg]),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(emp_table)
        elements.append(Spacer(1, 10))

        # Engagement Summary
        elements.append(Paragraph("Engagement & Q&A Summary", h2_style))
        elements.append(Paragraph(f"Attendee Questions Answered: <b>{report_data.get('questions_asked', 0)}</b>", body_style))

        doc.build(elements)
        logger.info(f"ReportService | PDF report compiled: {output_path}")
        return output_path

    def generate_docx_file(self, report_data: dict, output_path: Path) -> Path:
        """
        Generates standard OOXML (.docx) file natively with no third-party docx dependencies.
        """
        session_name = saxutils.escape(report_data.get("session_name", "Induction Session"))
        meeting = report_data.get("meeting", {})
        att = report_data.get("attendance", {})
        trainer = saxutils.escape(report_data.get("trainer", "KONE Trainer"))

        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

        rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

        # Build document XML
        body_xml = f"""
    <w:p>
      <w:pPr><w:jc w:val="left"/><w:spacing w:after="200"/></w:pPr>
      <w:r><w:rPr><w:b/><w:sz w:val="36"/><w:color w:val="0057B8"/></w:rPr><w:t>KONE AutoHR — Live Onboarding Session Report</w:t></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:spacing w:after="280"/></w:pPr>
      <w:r><w:rPr><w:b/><w:sz w:val="24"/><w:color w:val="1E293B"/></w:rPr><w:t>Session: {session_name}</w:t></w:r>
    </w:p>
    <w:p><w:r><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="0057B8"/></w:rPr><w:t>Session Details</w:t></w:r></w:p>
    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Meeting Date &amp; Time: </w:t></w:r><w:r><w:t>{saxutils.escape(meeting.get('meeting_date', 'N/A'))} @ {saxutils.escape(meeting.get('meeting_time', 'N/A'))}</w:t></w:r></w:p>
    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Teams URL: </w:t></w:r><w:r><w:t>{saxutils.escape(meeting.get('teams_meeting_url', 'N/A'))}</w:t></w:r></w:p>
    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>AI / Host Trainer: </w:t></w:r><w:r><w:t>{trainer}</w:t></w:r></w:p>
    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Verification Status: </w:t></w:r><w:r><w:t>{saxutils.escape(att.get('verification_status', 'N/A'))}</w:t></w:r></w:p>

    <w:p><w:pPr><w:spacing w:before="240"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="0057B8"/></w:rPr><w:t>Attendance Metrics</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Total Invited: {att.get('invited', 0)}</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Verified Attended: {att.get('verified_attended', 0)}</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Verified Absent: {att.get('verified_absent', 0)}</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Unverified: {att.get('unverified', 0)}</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Participation Rate: {att.get('participation_rate', 'N/A')}</w:t></w:r></w:p>

    <w:p><w:pPr><w:spacing w:before="240"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="0057B8"/></w:rPr><w:t>Attendee Roster</w:t></w:r></w:p>
"""
        for emp in att.get("list", []):
            emp_name = saxutils.escape(emp.get("name", ""))
            dept = saxutils.escape(emp.get("department", ""))
            role = saxutils.escape(emp.get("role", ""))
            status = saxutils.escape(emp.get("status", ""))
            body_xml += f"""    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>• {emp_name}</w:t></w:r><w:r><w:t> ({dept} - {role}): {status}</w:t></w:r></w:p>\n"""

        body_xml += f"""
    <w:p><w:pPr><w:spacing w:before="240"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="0057B8"/></w:rPr><w:t>Engagement &amp; Q&amp;A</w:t></w:r></w:p>
    <w:p><w:r><w:t>Questions Answered: {report_data.get('questions_asked', 0)}</w:t></w:r></w:p>
"""

        document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
{body_xml}
  </w:body>
</w:document>"""

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("word/document.xml", document_xml)

        logger.info(f"ReportService | DOCX report compiled: {output_path}")
        return output_path

    def get_or_generate_pdf(self, db: DBSession, session_id: str) -> Path:
        reports_dir = storage_service.get_reports_dir(session_id)
        pdf_path = reports_dir / "induction_report.pdf"
        if not pdf_path.exists():
            data = self.compile_session_report(db, session_id)
            self.generate_pdf_file(data, pdf_path)
        return pdf_path

    def get_or_generate_docx(self, db: DBSession, session_id: str) -> Path:
        reports_dir = storage_service.get_reports_dir(session_id)
        docx_path = reports_dir / "induction_report.docx"
        if not docx_path.exists():
            data = self.compile_session_report(db, session_id)
            self.generate_docx_file(data, docx_path)
        return docx_path

report_service = ReportService()
