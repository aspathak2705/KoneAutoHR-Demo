import datetime
from typing import Any, Dict, List
from app.schemas.common import BaseSchema

from pydantic import Field, field_validator
import json

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
    status: str

    @field_validator("questions_content", mode="before")
    @classmethod
    def parse_json_string(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v
