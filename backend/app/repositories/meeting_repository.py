from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import Optional, List
from app.models.meeting import Meeting

class MeetingRepository:
    def get(self, db: DBSession, id: str) -> Optional[Meeting]:
        stmt = select(Meeting).where(Meeting.id == id)
        return db.scalars(stmt).first()

    def get_by_session(self, db: DBSession, session_id: str) -> Optional[Meeting]:
        stmt = select(Meeting).where(Meeting.session_id == session_id).order_by(Meeting.created_at.desc())
        return db.scalars(stmt).first()

    def create(
        self,
        db: DBSession,
        session_id: str,
        graph_event_id: str,
        meeting_id: str,
        join_url: str,
        organizer: str,
        start_time: str,
        end_time: str
    ) -> Meeting:
        import datetime
        
        # Parse ISO format datetime strings to datetime objects if needed
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        db_obj = Meeting(
            session_id=session_id,
            graph_event_id=graph_event_id,
            meeting_id=meeting_id,
            join_url=join_url,
            organizer=organizer,
            start_time=start_time,
            end_time=end_time
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(self, db: DBSession, db_obj: Meeting, status: str) -> Meeting:
        db_obj.status = status
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
