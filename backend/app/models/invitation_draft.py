import datetime
import uuid
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class InvitationDraft(Base):
    __tablename__ = "invitation_drafts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    recipient_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recipient_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recipients: Mapped[Optional[str]] = mapped_column(String, nullable=True) # JSON array serialized to string
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="DRAFT") # DRAFT / EDITED / SENT
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationship
    session: Mapped["Session"] = relationship(back_populates="invitation_drafts")
