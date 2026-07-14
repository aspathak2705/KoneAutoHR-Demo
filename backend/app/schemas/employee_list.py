import datetime
from pydantic import Field
from app.schemas.common import BaseSchema, TimestampedSchema

class EmployeeListBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    original_filename: str
    storage_path: str

class EmployeeListCreate(EmployeeListBase):
    employee_count: int = 0

class EmployeeListResponse(BaseSchema):
    id: str
    name: str
    original_filename: str
    storage_path: str
    employee_count: int
    uploaded_at: datetime.datetime
    last_used: datetime.datetime
