import datetime
from typing import Optional
from app.schemas.common import BaseSchema

class MeetingCreate(BaseSchema):
    session_id: str
    teams_meeting_url: str
    meeting_passcode: Optional[str] = None
    organizer_name: str
    meeting_date: str
    meeting_time: str

    from pydantic import model_validator

    @model_validator(mode="after")
    def validate_meeting_url(self) -> "MeetingCreate":
        url = self.teams_meeting_url
        if "teams.microsoft.com" not in url and "teams.live.com" not in url and "localhost" not in url and "127.0.0.1" not in url:
            raise ValueError("Meeting URL must be a valid Microsoft Teams join link.")
        return self

class MeetingResponse(BaseSchema):
    id: str
    session_id: str
    teams_meeting_url: str
    meeting_passcode: Optional[str]
    organizer_name: str
    meeting_date: str
    meeting_time: str
    meeting_status: str
    created_at: datetime.datetime

class InvitationDraftResponse(BaseSchema):
    id: str
    session_id: str
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    recipients: Optional[str] = None
    subject: str
    body: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

class InvitationDraftUpdate(BaseSchema):
    subject: str
    body: str

class ReadinessResponse(BaseSchema):
    session_id: str
    has_presentation: bool
    has_employees: bool
    has_script: bool
    has_faq: bool
    has_meeting: bool
    is_ready: bool
