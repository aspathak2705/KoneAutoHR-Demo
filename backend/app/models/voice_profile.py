import datetime
import uuid
from typing import Optional
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String, default="sarvam")
    voice_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String, default="en-IN")
    status: Mapped[str] = mapped_column(String, default="inactive")  # "active" or "inactive"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    last_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
