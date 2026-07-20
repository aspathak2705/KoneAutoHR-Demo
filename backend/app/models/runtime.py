import datetime
import uuid
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Runtime(Base):
    __tablename__ = "runtimes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String, default="IDLE") 
    # State values: IDLE, PREPARING, READY, WAITING_FOR_TIME, SCHEDULED, LAUNCHING, JOINING, CONNECTED, WAITING, DISCONNECTED, RECONNECTING, COMPLETED, FAILED
    
    current_step: Mapped[str] = mapped_column(String, default="IDLE", nullable=True)
    meeting_status: Mapped[str] = mapped_column(String, default="DISCONNECTED", nullable=True)
    
    current_slide: Mapped[int] = mapped_column(Integer, default=0)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0)
    speech_state: Mapped[str] = mapped_column(String, default="IDLE") # IDLE, SPEAKING, INTERRUPTED
    
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    connected_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    last_heartbeat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(String, nullable=True)

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="runtimes")
