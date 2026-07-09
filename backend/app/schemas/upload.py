import datetime
from app.schemas.common import BaseSchema
from app.core.constants import UploadType

class UploadResponse(BaseSchema):
    id: str
    session_id: str
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    upload_type: UploadType
    created_at: datetime.datetime
