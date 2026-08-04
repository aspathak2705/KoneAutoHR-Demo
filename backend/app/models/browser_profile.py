import datetime
import uuid
from typing import Optional
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class BrowserProfile(Base):
    __tablename__ = "browser_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_name: Mapped[str] = mapped_column(String, default="msedge")
    edge_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")  # "active", "inactive"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    last_verified_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
