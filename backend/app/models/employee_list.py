import datetime
import uuid
from typing import List
from sqlalchemy import String, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class EmployeeList(Base):
    __tablename__ = "employee_lists"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, index=True)
    original_filename: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationship
    sessions: Mapped[List["Session"]] = relationship(back_populates="employee_list")
