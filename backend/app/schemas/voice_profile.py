import datetime
from typing import Optional
from app.schemas.common import BaseSchema

class VoiceProfileBase(BaseSchema):
    display_name: str
    language: str = "en-IN"

class VoiceProfileCreate(VoiceProfileBase):
    provider: str = "sarvam"
    voice_id: str
    status: str = "inactive"

class VoiceProfileResponse(BaseSchema):
    id: str
    provider: str
    voice_id: str
    display_name: str
    language: str
    status: str
    created_at: datetime.datetime
    last_verified_at: Optional[datetime.datetime]
