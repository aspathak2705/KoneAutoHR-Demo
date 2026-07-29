import datetime
from typing import Optional
from pydantic import Field
from app.schemas.common import BaseSchema

class AgentConfigurationBase(BaseSchema):
    provider: str = Field("microsoft", max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    tenant: Optional[str] = Field(None, max_length=255)
    profile_path: Optional[str] = Field(None, max_length=255)
    is_connected: bool = Field(False)

class AgentConfigurationCreate(AgentConfigurationBase):
    pass

class AgentConfigurationUpdate(AgentConfigurationBase):
    pass

class AgentConfigurationResponse(AgentConfigurationBase):
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
