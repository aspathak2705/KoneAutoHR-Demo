from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from typing import List
from app.db.database import get_db
from app.schemas.meeting import MeetingCreate, MeetingResponse
from app.repositories.meeting_repository import meeting_repository
from app.integrations.microsoft.microsoft_gateway import microsoft_gateway
from app.integrations.microsoft.graph_client import microsoft_graph_client
from app.integrations.microsoft.auth import microsoft_auth_manager

router = APIRouter(prefix="/meetings", tags=["Meeting Management"])

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(meeting_in: MeetingCreate, db: DBSession = Depends(get_db)):
    # Verify Microsoft Auth configuration and token
    if not microsoft_auth_manager.get_access_token():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft integration not authenticated. Connect via OAuth first."
        )

    try:
        # Fetch organizer details using Graph profile
        profile = await microsoft_graph_client.get_profile()
        organizer = profile.get("mail") or profile.get("userPrincipalName") or "hr@kone.com"
        
        # 1. Schedule Microsoft Teams online meeting
        online_meet = await microsoft_gateway.meeting.create_online_meeting(
            subject=meeting_in.subject,
            start_time=meeting_in.start_time,
            end_time=meeting_in.end_time
        )
        meeting_id = online_meet.get("id")
        join_url = online_meet.get("joinWebUrl")
        
        # 2. Create Outlook Calendar event including join URL
        calendar_body = f"<p>Join the Kone AutoHR Induction Session here: <a href='{join_url}'>{join_url}</a></p>"
        calendar_event = await microsoft_gateway.calendar.create_event(
            subject=meeting_in.subject,
            start_time=meeting_in.start_time,
            end_time=meeting_in.end_time,
            body_content=calendar_body
        )
        graph_event_id = calendar_event.get("id")
        
        # 3. Persist to SQLite database
        db_meeting = meeting_repository.create(
            db=db,
            session_id=meeting_in.session_id,
            graph_event_id=graph_event_id,
            meeting_id=meeting_id,
            join_url=join_url,
            organizer=organizer,
            start_time=meeting_in.start_time,
            end_time=meeting_in.end_time
        )
        return db_meeting

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Microsoft Graph scheduling failure: {str(e)}"
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

@router.post("/{id}/join", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def join_meeting(id: str, db: DBSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Resource not prepared")

@router.post("/{id}/leave", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def leave_meeting(id: str, db: DBSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Resource not prepared")

@router.post("/{id}/send-invites", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def send_invitations(id: str, db: DBSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Resource not prepared")

@router.get("/{id}/invitations", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_invitations(id: str, db: DBSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Resource not prepared")
