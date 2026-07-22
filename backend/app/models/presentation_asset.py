import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class PresentationAsset(Base):
    __tablename__ = "presentation_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    presentation_id: Mapped[str] = mapped_column(String, ForeignKey("presentations.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String)  # presentation, video, image, notes, script
    storage_provider: Mapped[str] = mapped_column(String, default="LOCAL")  # LOCAL, S3, AZURE, NAS
    storage_uri: Mapped[str] = mapped_column(String)
    checksum: Mapped[str] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationship
    presentation: Mapped["Presentation"] = relationship(back_populates="assets")
