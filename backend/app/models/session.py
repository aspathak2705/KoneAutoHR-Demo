import datetime
import uuid
from typing import List, Optional
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="PENDING") # SessionStatus enum value
    scheduled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Foreign Keys
    presentation_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("presentations.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_list_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("employee_lists.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    presentation: Mapped[Optional["Presentation"]] = relationship(back_populates="sessions")
    employee_list: Mapped[Optional["EmployeeList"]] = relationship(back_populates="sessions")
    uploads: Mapped[List["Upload"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    presentation_jobs: Mapped[List["PresentationJob"]] = relationship(back_populates="session", cascade="all, delete-orphan")
