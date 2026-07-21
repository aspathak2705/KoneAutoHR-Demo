import re
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.models.meeting import Meeting
from app.models.session import Session as DBSessionModel

class MeetingRepository:
    def get(self, db: DBSession, id: str) -> Optional[Meeting]:
        stmt = select(Meeting).where(Meeting.id == id)
        return db.scalars(stmt).first()

    def get_by_session(self, db: DBSession, session_id: str) -> Optional[Meeting]:
        stmt = select(Meeting).where(Meeting.session_id == session_id).order_by(Meeting.created_at.desc())
        return db.scalars(stmt).first()

    def validate_meeting(self, db: DBSession, session_id: str, teams_meeting_url: str) -> None:
        # 1. URL Exists
        if not teams_meeting_url or not teams_meeting_url.strip():
            raise ValueError("Teams Meeting URL cannot be empty.")
            
        # 2. Teams URL Format
        # Match teams.microsoft.com or teams.live.com (allowing http/https prefixes)
        teams_pattern = r"^https?://([a-zA-Z0-9-]+\.)?teams\.(microsoft|live)\.com/.*$"
        if not re.match(teams_pattern, teams_meeting_url.strip()):
            raise ValueError("Invalid Teams Meeting URL format. Must be a valid Microsoft Teams link.")

        # 3. Session Association (ensure session exists)
        session_exists = db.query(DBSessionModel).filter(DBSessionModel.id == session_id).first()
        if not session_exists:
            raise ValueError("Associated session not found.")

        # 4. Duplicate Meetings (clean up stale association if reusing same real Teams URL)
        duplicate = db.query(Meeting).filter(
            Meeting.teams_meeting_url == teams_meeting_url.strip(),
            Meeting.session_id != session_id
        ).first()
        if duplicate:
            db.delete(duplicate)
            db.commit()

    def create_or_update(
        self,
        db: DBSession,
        session_id: str,
        teams_meeting_url: str,
        meeting_passcode: Optional[str],
        organizer_name: str,
        meeting_date: str,
        meeting_time: str
    ) -> Meeting:
        self.validate_meeting(db, session_id, teams_meeting_url)

        # Check if a meeting record already exists for this session
        db_obj = self.get_by_session(db, session_id)
        if db_obj:
            # Update existing
            db_obj.teams_meeting_url = teams_meeting_url.strip()
            db_obj.meeting_passcode = meeting_passcode.strip() if meeting_passcode else None
            db_obj.organizer_name = organizer_name.strip()
            db_obj.meeting_date = meeting_date.strip()
            db_obj.meeting_time = meeting_time.strip()
            db_obj.meeting_status = "PENDING"
        else:
            # Create new
            db_obj = Meeting(
                session_id=session_id,
                teams_meeting_url=teams_meeting_url.strip(),
                meeting_passcode=meeting_passcode.strip() if meeting_passcode else None,
                organizer_name=organizer_name.strip(),
                meeting_date=meeting_date.strip(),
                meeting_time=meeting_time.strip()
            )
            db.add(db_obj)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(self, db: DBSession, db_obj: Meeting, status: str) -> Meeting:
        db_obj.meeting_status = status
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: DBSession, id: str) -> None:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.commit()

meeting_repository = MeetingRepository()
