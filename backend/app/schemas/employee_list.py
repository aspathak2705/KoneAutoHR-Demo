import datetime
from pydantic import Field
from app.schemas.common import BaseSchema, TimestampedSchema

class EmployeeListBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    original_filename: str
    storage_path: str

class EmployeeListCreate(EmployeeListBase):
    employee_count: int = 0

class EmployeeListResponse(TimestampedSchema):
    id: str
    name: str
    original_filename: str
    storage_path: str
    employee_count: int
    last_used: datetime.datetime
