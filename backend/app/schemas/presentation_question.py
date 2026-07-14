import datetime
from typing import Any, Dict, List
from app.schemas.common import BaseSchema

class PresentationQuestionBase(BaseSchema):
    presentation_id: str
    questions_content: List[Dict[str, Any]]

class PresentationQuestionCreate(PresentationQuestionBase):
    pass

class PresentationQuestionUpdate(BaseSchema):
    questions_content: List[Dict[str, Any]]

class PresentationQuestionResponse(BaseSchema):
    id: str
    presentation_id: str
    questions_content: List[Dict[str, Any]]
    generated_at: datetime.datetime
    editable: bool
    is_active: bool
