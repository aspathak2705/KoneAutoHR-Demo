import datetime
from typing import Any, Dict
from app.schemas.common import BaseSchema

from pydantic import Field, field_validator
import json

class PresentationScriptBase(BaseSchema):
    presentation_id: str
    script_content: Dict[str, Any]
    llm_model: str

class PresentationScriptCreate(PresentationScriptBase):
    pass

class PresentationScriptUpdate(BaseSchema):
    script_content: Dict[str, Any]

class PresentationScriptResponse(BaseSchema):
    id: str
    presentation_id: str
    script_content: Dict[str, Any]
    generated_at: datetime.datetime
    llm_model: str
    editable: bool
    status: str

    @field_validator("script_content", mode="before")
    @classmethod
    def parse_json_string(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v
