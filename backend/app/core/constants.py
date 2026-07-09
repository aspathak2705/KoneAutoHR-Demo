from enum import Enum

class SessionStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class UploadType(str, Enum):
    PRESENTATION = "PRESENTATION"
    EMPLOYEES = "EMPLOYEES"
    VIDEO = "VIDEO"

class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
