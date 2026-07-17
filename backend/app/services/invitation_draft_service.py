from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.invitation_draft import InvitationDraft
from app.models.session import Session as DBSessionModel
from app.models.meeting import Meeting
from app.models.organization_config import OrganizationConfig
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.modules.induction.llm.client import llm_client
from loguru import logger
import datetime

class InvitationDraftService:
    def get_drafts_by_session(self, db: DBSession, session_id: str) -> List[InvitationDraft]:
        return db.query(InvitationDraft).filter(InvitationDraft.session_id == session_id).all()

    def update_draft(self, db: DBSession, draft_id: str, subject: str, body: str) -> InvitationDraft:
        draft = db.query(InvitationDraft).filter(InvitationDraft.id == draft_id).first()
        if not draft:
            raise ValueError("Invitation draft not found.")
        draft.subject = subject
        draft.body = body
        draft.status = "EDITED"
        db.commit()
        db.refresh(draft)
        return draft

    async def generate_drafts_for_session(self, db: DBSession, session_id: str) -> List[InvitationDraft]:
        # 1. Fetch Session and Meeting
        session = db.query(DBSessionModel).filter(DBSessionModel.id == session_id).first()
        if not session:
            raise ValueError("Session not found.")
        if not session.employee_list:
            raise ValueError("Session does not have an employee list uploaded.")
            
        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        if not meeting:
            raise ValueError("Meeting details must be configured before generating drafts.")

        # 2. Fetch Organization Config
        config = db.query(OrganizationConfig).first()
        if not config:
            # Create a default fallback config
            config = OrganizationConfig(
                company_name="KONE",
                company_domain="kone.com",
                ai_officer_name="KONE HR Officer",
                ai_trainer_name="KONE Trainer",
                ai_role_description="AI Onboarding Assistant",
                vocal_tone="Professional",
                communication_style="Direct"
            )

        # 3. Parse Employees
        try:
            employees = parse_employees_excel(session.employee_list.storage_path)
        except Exception as e:
            raise ValueError(f"Failed to parse employees register: {str(e)}")

        # 4. Clear any existing drafts for this session to prevent duplicates
        db.query(InvitationDraft).filter(InvitationDraft.session_id == session_id).delete()
        db.commit()

        drafts = []
        # 5. Generate a draft for each employee
        for emp in employees:
            recipient_name = emp.get("name", "New Employee")
            recipient_email = emp.get("email")
            if not recipient_email:
                continue

            subject = f"Welcome to {config.company_name}! Induction Training Invitation"
            body = (
                f"<p>Dear {recipient_name},</p>"
                f"<p>Welcome to {config.company_name}! We are excited to invite you to your upcoming induction session: <b>{session.name}</b>.</p>"
                f"<p><b>Date:</b> {meeting.meeting_date}<br>"
                f"<b>Time:</b> {meeting.meeting_time}<br>"
                f"<b>Teams Meeting URL:</b> <a href='{meeting.teams_meeting_url}'>{meeting.teams_meeting_url}</a><br>"
                f"<b>Passcode:</b> {meeting.meeting_passcode or 'None'}</p>"
                f"<p>Best regards,<br>{config.ai_trainer_name}<br>HR Onboarding Assistant</p>"
            )

            # Attempt LLM personalization if API key is present
            if llm_client.api_key:
                prompt = f"""
                You are an HR Assistant named {config.ai_trainer_name} at {config.company_name}.
                Generate a personalized, warm induction invitation email draft for the following employee:
                - Name: {recipient_name}
                - Email: {recipient_email}
                - Department: {emp.get('department', 'General')}
                - Role/Designation: {emp.get('designation', 'New Hire')}
                - Joining Date: {emp.get('joining_date', 'Soon')}

                Meeting Details:
                - Topic: {session.name}
                - Date: {meeting.meeting_date}
                - Time: {meeting.meeting_time}
                - Teams URL: {meeting.teams_meeting_url}
                - Passcode: {meeting.meeting_passcode or "None required"}

                Company Tone: {config.vocal_tone}
                Company Style: {config.communication_style}

                Format the output strictly as a JSON object matching this schema:
                {{
                  "subject": "Email subject string",
                  "body": "Complete email body string, using HTML paragraphs (<p>) and line breaks (<br>)."
                }}
                Do not include markdown code block syntax. Only output raw JSON.
                """
                try:
                    res = await llm_client.generate_json(prompt, name=f"draft_{recipient_email}")
                    if res and "subject" in res and "body" in res:
                        subject = res["subject"]
                        body = res["body"]
                except Exception as e:
                    logger.warning(f"LLM draft generation failed for {recipient_email}, falling back to template: {e}")

            db_draft = InvitationDraft(
                session_id=session_id,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                status="DRAFT"
            )
            db.add(db_draft)
            drafts.append(db_draft)

        db.commit()
        return drafts

invitation_draft_service = InvitationDraftService()
