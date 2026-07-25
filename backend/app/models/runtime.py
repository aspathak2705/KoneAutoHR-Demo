import datetime
import uuid
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Runtime(Base):
    __tablename__ = "runtimes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    
    # Main state machine (13 locked states)
    state: Mapped[str] = mapped_column(String, default="NOT_CREATED")
    # NOT_CREATED, PREPARING, READY, STARTING, BROWSER_READY, JOINING, WAITING, CONNECTED, PRESENTING, FINISHED, STOPPING, STOPPED, FAILED
    
    # Detailed tracking for state machine transitions
    browser_state: Mapped[str] = mapped_column(String, default="NOT_CREATED", nullable=True)
    induction_state: Mapped[str] = mapped_column(String, default="NOT_CREATED", nullable=True)
    
    # Presentation tracking
    current_slide: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error tracking
    last_error: Mapped[str] = mapped_column(String, nullable=True)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Legacy fields (kept for backward compatibility during migration)
    meeting_status: Mapped[str] = mapped_column(String, default="DISCONNECTED", nullable=True)
    speech_state: Mapped[str] = mapped_column(String, default="IDLE", nullable=True)  # IDLE, SPEAKING, INTERRUPTED
    
    # Timestamps
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    connected_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    last_heartbeat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="runtimes")
