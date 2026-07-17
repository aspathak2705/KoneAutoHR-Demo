import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class RuntimeMessage(Base):
    __tablename__ = "runtime_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    speaker_name: Mapped[str] = mapped_column(String, nullable=False) # Name of Employee or "AI Assistant"
    message_text: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="runtime_messages")
