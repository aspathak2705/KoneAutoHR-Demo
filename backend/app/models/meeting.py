import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    teams_meeting_url: Mapped[str] = mapped_column(String, nullable=False)
    meeting_passcode: Mapped[str] = mapped_column(String, nullable=True)
    organizer_name: Mapped[str] = mapped_column(String, nullable=False)
    meeting_date: Mapped[str] = mapped_column(String, nullable=False) # Format: YYYY-MM-DD
    meeting_time: Mapped[str] = mapped_column(String, nullable=False) # Format: HH:MM
    meeting_status: Mapped[str] = mapped_column(String, default="PENDING")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="meetings")
