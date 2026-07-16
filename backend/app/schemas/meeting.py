import datetime
from app.schemas.common import BaseSchema

class MeetingCreate(BaseSchema):
    session_id: str
    subject: str
    start_time: datetime.datetime
    end_time: datetime.datetime

class MeetingResponse(BaseSchema):
    id: str
    session_id: str
    graph_event_id: str
    meeting_id: str
    join_url: str
    organizer: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    status: str
    created_at: datetime.datetime
