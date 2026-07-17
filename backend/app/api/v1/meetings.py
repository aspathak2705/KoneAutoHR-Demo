from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from typing import List
from app.db.database import get_db
from app.schemas.meeting import (
    MeetingCreate,
    MeetingResponse,
    InvitationDraftResponse,
    InvitationDraftUpdate,
    ReadinessResponse
)
from app.repositories.meeting_repository import meeting_repository
from app.services.invitation_draft_service import invitation_draft_service
from app.services.session_service import session_service

router = APIRouter(prefix="/meetings", tags=["Meeting Management"])

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(meeting_in: MeetingCreate, db: DBSession = Depends(get_db)):
    try:
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

@router.get("/session/{session_id}", response_model=MeetingResponse)
def get_meeting_by_session(session_id: str, db: DBSession = Depends(get_db)):
    db_meeting = meeting_repository.get_by_session(db, session_id)
    if not db_meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No meeting configured for this session."
        )
    return db_meeting

@router.post("/session/{session_id}/generate-drafts", response_model=List[InvitationDraftResponse])
async def generate_invitation_drafts(session_id: str, db: DBSession = Depends(get_db)):
    try:
        drafts = await invitation_draft_service.generate_drafts_for_session(db, session_id)
        return drafts
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/session/{session_id}/drafts", response_model=List[InvitationDraftResponse])
def get_invitation_drafts(session_id: str, db: DBSession = Depends(get_db)):
    return invitation_draft_service.get_drafts_by_session(db, session_id)

@router.put("/drafts/{draft_id}", response_model=InvitationDraftResponse)
def update_invitation_draft(draft_id: str, draft_in: InvitationDraftUpdate, db: DBSession = Depends(get_db)):
    try:
        return invitation_draft_service.update_draft(
            db=db,
            draft_id=draft_id,
            subject=draft_in.subject,
            body=draft_in.body
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.post("/session/{session_id}/validate-readiness", response_model=ReadinessResponse)
def validate_session_readiness(session_id: str, db: DBSession = Depends(get_db)):
    try:
        result = session_service.validate_readiness(db, session_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
