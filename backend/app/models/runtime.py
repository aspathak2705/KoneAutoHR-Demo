import datetime
import uuid
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Runtime(Base):
    __tablename__ = "runtimes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String, default="PREPARING") # PREPARING / READY / JOINING / PRESENTING / QUESTIONS / COMPLETED
    current_slide: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    last_heartbeat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="runtimes")
