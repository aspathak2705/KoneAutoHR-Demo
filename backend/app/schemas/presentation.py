import datetime
from typing import Optional
from pydantic import Field
from app.schemas.common import BaseSchema, TimestampedSchema

class PresentationBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    original_filename: str
    storage_path: str
    uploaded_by: Optional[str] = None

class PresentationCreate(PresentationBase):
    pass

class PresentationResponse(BaseSchema):
    id: str
    name: str
    original_filename: str
    storage_path: str
    uploaded_by: Optional[str] = None
    uploaded_at: datetime.datetime
    last_used: datetime.datetime
    session_count: int
