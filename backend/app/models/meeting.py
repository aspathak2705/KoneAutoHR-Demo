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

    # Property Aliases for backward compatibility & test suites
    @property
    def teams_url(self) -> str:
        return self.teams_meeting_url

    @teams_url.setter
    def teams_url(self, val: str):
        self.teams_meeting_url = val

    @property
    def date(self) -> str:
        return self.meeting_date

    @date.setter
    def date(self, val: str):
        self.meeting_date = val

    @property
    def time(self) -> str:
        return self.meeting_time

    @time.setter
    def time(self, val: str):
        self.meeting_time = val

    @property
    def organizer(self) -> str:
        return self.organizer_name

    @organizer.setter
    def organizer(self, val: str):
        self.organizer_name = val

    def __init__(self, **kwargs):
        # Allow initializing with either teams_url/date/time/organizer or teams_meeting_url/meeting_date/meeting_time/organizer_name
        if "teams_url" in kwargs and "teams_meeting_url" not in kwargs:
            kwargs["teams_meeting_url"] = kwargs.pop("teams_url")
        if "date" in kwargs and "meeting_date" not in kwargs:
            kwargs["meeting_date"] = kwargs.pop("date")
        if "time" in kwargs and "meeting_time" not in kwargs:
            kwargs["meeting_time"] = kwargs.pop("time")
        if "organizer" in kwargs and "organizer_name" not in kwargs:
            kwargs["organizer_name"] = kwargs.pop("organizer")
        super().__init__(**kwargs)
