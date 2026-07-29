import datetime
import uuid
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class AgentConfiguration(Base):
    __tablename__ = "agent_configuration"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String, default="microsoft")
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tenant: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    profile_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
