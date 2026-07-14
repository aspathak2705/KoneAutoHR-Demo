import datetime
from typing import Any, Dict
from app.schemas.common import BaseSchema

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
    is_active: bool
