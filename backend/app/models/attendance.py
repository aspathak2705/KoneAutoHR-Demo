import datetime
import uuid
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Attendance(Base):
    __tablename__ = "attendances"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    attendee_name: Mapped[str] = mapped_column(String, nullable=False)
    attendee_email: Mapped[str] = mapped_column(String, nullable=False)
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    left_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    questions_asked: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="UNKNOWN") # PRESENT / PARTIAL / LEFT_EARLY / UNKNOWN

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="attendances")
