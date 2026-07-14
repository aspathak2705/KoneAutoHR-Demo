import datetime
from typing import List, Optional
from pydantic import Field
from app.schemas.common import BaseSchema, TimestampedSchema
from app.core.constants import SessionStatus
from app.schemas.upload import UploadResponse
from app.schemas.presentation_job import PresentationJobResponse
from app.schemas.presentation import PresentationResponse
from app.schemas.employee_list import EmployeeListResponse

class SessionBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    scheduled_at: Optional[datetime.datetime] = None

class SessionCreate(SessionBase):
    presentation_id: Optional[str] = None
    employee_list_id: Optional[str] = None

class SessionUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[SessionStatus] = None
    scheduled_at: Optional[datetime.datetime] = None
    presentation_id: Optional[str] = None
    employee_list_id: Optional[str] = None

class SessionResponse(TimestampedSchema):
    id: str
    name: str
    status: SessionStatus
    scheduled_at: Optional[datetime.datetime] = None
    presentation_id: Optional[str] = None
    employee_list_id: Optional[str] = None

class SessionDetailResponse(SessionResponse):
    uploads: List[UploadResponse] = []
    presentation_jobs: List[PresentationJobResponse] = []
    presentation: Optional[PresentationResponse] = None
    employee_list: Optional[EmployeeListResponse] = None
