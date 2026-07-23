from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from typing import List
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

@router.post("/session/{session_id}/generate-drafts", response_model=List[InvitationDraftResponse])
async def generate_invitation_drafts(session_id: str, db: DBSession = Depends(get_db)):
    # Microsoft Graph integration removed; return empty drafts list
    return []

@router.get("/session/{session_id}/drafts", response_model=List[InvitationDraftResponse])
def get_invitation_drafts(session_id: str, db: DBSession = Depends(get_db)):
    # Microsoft Graph integration removed; return empty drafts list
    return []

@router.put("/drafts/{draft_id}", response_model=InvitationDraftResponse)
def update_invitation_draft(draft_id: str, draft_in: InvitationDraftUpdate, db: DBSession = Depends(get_db)):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Invitation drafts are disabled as Microsoft Graph integration is removed."
    )

from app.services.runtime_context_service import runtime_context_service
from app.services.runtime_readiness_service import runtime_readiness_service

@router.post("/session/{session_id}/validate-readiness")
def validate_session_readiness(session_id: str, db: DBSession = Depends(get_db)):
    """
    Phase 4 — Unified Readiness API
    """
    context = runtime_context_service.build_runtime_context(db, session_id)
    return runtime_readiness_service.evaluate_readiness(context)
