import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    graph_event_id: Mapped[str] = mapped_column(String, nullable=False)
    meeting_id: Mapped[str] = mapped_column(String, nullable=False)
    join_url: Mapped[str] = mapped_column(String, nullable=False)
    organizer: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String, default="SCHEDULED")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="meetings")
