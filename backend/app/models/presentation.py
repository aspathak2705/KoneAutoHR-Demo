import datetime
import uuid
from typing import List, Optional
from sqlalchemy import String, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Presentation(Base):
    __tablename__ = "presentations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, index=True)
    original_filename: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    last_used: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    session_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    metadata_records: Mapped[List["PresentationMetadata"]] = relationship(back_populates="presentation", cascade="all, delete-orphan")
    scripts: Mapped[List["PresentationScript"]] = relationship(back_populates="presentation", cascade="all, delete-orphan")
    questions: Mapped[List["PresentationQuestion"]] = relationship(back_populates="presentation", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship(back_populates="presentation")
    assets: Mapped[List["PresentationAsset"]] = relationship(back_populates="presentation", cascade="all, delete-orphan")
