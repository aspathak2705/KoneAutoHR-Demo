import datetime
import uuid
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class PresentationMetadata(Base):
    __tablename__ = "presentation_metadata"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    presentation_id: Mapped[str] = mapped_column(String, ForeignKey("presentations.id", ondelete="CASCADE"), index=True)
    slide_count: Mapped[int] = mapped_column(Integer, default=0)
    generation_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    generation_status: Mapped[str] = mapped_column(String, default="PENDING")
    package_version: Mapped[str] = mapped_column(String, default="1.0.0")
    last_ai_generation: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationship
    presentation: Mapped["Presentation"] = relationship(back_populates="metadata_records")
