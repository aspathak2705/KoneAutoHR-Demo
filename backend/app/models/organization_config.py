import datetime
import uuid
from typing import Optional
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class OrganizationConfig(Base):
    __tablename__ = "organization_config"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    company_domain: Mapped[str] = mapped_column(String, nullable=False)
    ai_officer_name: Mapped[str] = mapped_column(String, nullable=False)
    ai_trainer_name: Mapped[str] = mapped_column(String, nullable=False)
    ai_role_description: Mapped[str] = mapped_column(String, nullable=False)
    vocal_tone: Mapped[str] = mapped_column(String, nullable=False)
    communication_style: Mapped[str] = mapped_column(String, nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
