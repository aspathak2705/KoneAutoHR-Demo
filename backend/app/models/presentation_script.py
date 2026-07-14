import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class PresentationScript(Base):
    __tablename__ = "presentation_scripts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    presentation_id: Mapped[str] = mapped_column(String, ForeignKey("presentations.id", ondelete="CASCADE"), index=True)
    script_content: Mapped[str] = mapped_column(Text) # Stored JSON payload containing WelcomeFlow, SlideNarrations, Closing
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    llm_model: Mapped[str] = mapped_column(String)
    editable: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="ACTIVE") # ACTIVE, ARCHIVED, DRAFT

    # Relationship
    presentation: Mapped["Presentation"] = relationship(back_populates="scripts")
