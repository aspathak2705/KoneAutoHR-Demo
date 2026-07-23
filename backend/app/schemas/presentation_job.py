import datetime
from typing import Optional
from app.schemas.common import TimestampedSchema
from app.core.constants import JobStatus

class PresentationJobResponse(TimestampedSchema):
    id: str
    session_id: str
    status: JobStatus
    progress: float
    job_type: str
    error_message: Optional[str] = None
