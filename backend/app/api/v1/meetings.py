from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
import json
from pydantic import BaseModel
from app.db.database import get_db
from app.schemas.meeting import (
    MeetingCreate,
    MeetingResponse,
    InvitationDraftResponse,
    InvitationDraftUpdate
)
from app.repositories.meeting_repository import meeting_repository
from app.services.session_service import session_service
from app.db.unit_of_work import UnitOfWork
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.invitation_draft import InvitationDraft
from app.modules.induction.employees.excel_parser import parse_employees_excel

router = APIRouter(prefix="/meetings", tags=["Meeting Management"])

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(meeting_in: MeetingCreate, db: DBSession = Depends(get_db)):
    try:
        with UnitOfWork(db):
            db_meeting = meeting_repository.create_or_update(
                db=db,
                session_id=meeting_in.session_id,
                teams_meeting_url=meeting_in.teams_meeting_url,
                meeting_passcode=meeting_in.meeting_passcode,
                organizer_name=meeting_in.organizer_name,
                meeting_date=meeting_in.meeting_date,
                meeting_time=meeting_in.meeting_time
            )
        return db_meeting
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{id}", response_model=MeetingResponse)
def get_meeting(id: str, db: DBSession = Depends(get_db)):
    db_meeting = meeting_repository.get(db, id)
    if not db_meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting record not found."
        )
    return db_meeting

@router.get("/session/{session_id}")
def get_meeting_by_session(session_id: str, db: DBSession = Depends(get_db)):
    """
    Phase 6 — Meeting API Refactor
    """
    db_meeting = meeting_repository.get_by_session(db, session_id)
    if not db_meeting:
        return {
            "configured": False,
            "meeting": None,
            "session_id": session_id
        }
    return {
        "configured": True,
        "session_id": session_id,
        "id": db_meeting.id,
        "teams_meeting_url": db_meeting.teams_meeting_url,
        "meeting_passcode": db_meeting.meeting_passcode,
        "meeting_date": db_meeting.meeting_date,
        "meeting_time": db_meeting.meeting_time,
        "organizer_name": db_meeting.organizer_name
    }

class GenerateDraftRequest(BaseModel):
    employee_ids: Optional[List[str]] = None

@router.post("/session/{session_id}/generate-drafts", response_model=List[InvitationDraftResponse])
async def generate_invitation_drafts(session_id: str, req: Optional[GenerateDraftRequest] = None, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    if not session.employee_list:
        raise HTTPException(status_code=400, detail="Employee list not uploaded yet.")
    
    meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
    meeting_url = meeting.teams_meeting_url if meeting else "https://teams.microsoft.com/l/meetup-join/dummy"
    meeting_date = meeting.meeting_date if meeting else "TBD"
    meeting_time = meeting.meeting_time if meeting else "TBD"
    organizer = meeting.organizer_name if meeting else "KONE Trainer"
    passcode_info = f"<p>Meeting Passcode: <code>{meeting.meeting_passcode}</code></p>" if (meeting and meeting.meeting_passcode) else ""

    try:
        employees = parse_employees_excel(session.employee_list.storage_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse employee Excel: {e}")

    selected_emails = []
    missing_email_count = 0
    
    target_ids = req.employee_ids if req else None
    
    for idx, emp in enumerate(employees):
        emp_id = emp.get("id") or emp.get("employee_id") or str(idx + 1)
        if target_ids is not None and emp_id not in target_ids:
            continue
            
        email = emp.get("email")
        if not email:
            missing_email_count += 1
            continue
        
        email_clean = email.strip()
        if email_clean and email_clean not in selected_emails:
            selected_emails.append(email_clean)

    if not selected_emails:
        raise HTTPException(status_code=400, detail="No valid email addresses found or selected.")

    # Remove existing drafts
    db.query(InvitationDraft).filter(InvitationDraft.session_id == session_id).delete()
    db.commit()

    subject = f"KONE Induction Invitation — Team Session"
    body = (
        f"<p>Dear Team,</p>"
        f"<p>You are invited to attend the upcoming KONE employee induction session.</p>"
        f"<p>This session will cover key onboarding items, safety guidelines, and company guidelines to kickstart your journey at KONE.</p>"
        f"<p><strong>Session details:</strong></p>"
        f"<ul>"
        f"<li>Date: <strong>{meeting_date}</strong></li>"
        f"<li>Time: <strong>{meeting_time}</strong></li>"
        f"<li>Host: <strong>{organizer}</strong></li>"
        f"</ul>"
        f"<p>Please join the session using the Microsoft Teams link below:</p>"
        f"<p><a href=\"{meeting_url}\" target=\"_blank\" style=\"display:inline-block;background-color:#0078d4;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;font-weight:bold;\">Join Induction Meeting</a></p>"
        f"{passcode_info}"
        f"<p>Please ensure you join the session on time.</p>"
        f"<p>Best regards,<br/>KONE HR Team</p>"
    )

    with UnitOfWork(db):
        draft = InvitationDraft(
            session_id=session_id,
            recipient_name="Team",
            recipient_email=", ".join(selected_emails),
            recipients=json.dumps(selected_emails),
            subject=subject,
            body=body,
            status="DRAFT"
        )
        db.add(draft)
    
    db.refresh(draft)
    
    return [draft]

@router.get("/session/{session_id}/drafts", response_model=List[InvitationDraftResponse])
def get_invitation_drafts(session_id: str, db: DBSession = Depends(get_db)):
    drafts = db.query(InvitationDraft).filter(InvitationDraft.session_id == session_id).all()
    return drafts

@router.put("/drafts/{draft_id}", response_model=InvitationDraftResponse)
def update_invitation_draft(draft_id: str, draft_in: InvitationDraftUpdate, db: DBSession = Depends(get_db)):
    draft = db.query(InvitationDraft).filter(InvitationDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Invitation draft not found.")
    
    with UnitOfWork(db):
        draft.subject = draft_in.subject
        draft.body = draft_in.body
        draft.status = "EDITED"
    
    db.refresh(draft)
    return draft

from app.services.runtime_context_service import runtime_context_service
from app.services.runtime_readiness_service import runtime_readiness_service

@router.post("/session/{session_id}/validate-readiness")
def validate_session_readiness(session_id: str, db: DBSession = Depends(get_db)):
    """
    Phase 4 — Unified Readiness API
    """
    context = runtime_context_service.build_runtime_context(db, session_id)
    return runtime_readiness_service.evaluate_readiness(context)
