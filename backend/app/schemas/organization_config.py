import datetime
from typing import Optional
from pydantic import Field, field_validator
from app.schemas.common import BaseSchema

class OrganizationConfigBase(BaseSchema):
    company_name: str = Field(..., min_length=1, max_length=100)
    company_domain: str = Field(..., min_length=3, max_length=100)
    ai_officer_name: str = Field(..., min_length=1, max_length=100)
    ai_trainer_name: str = Field(..., min_length=1, max_length=100)
    ai_role_description: str = Field(..., min_length=1, max_length=255)
    vocal_tone: str = Field(..., min_length=1, max_length=100)
    communication_style: str = Field(..., min_length=1, max_length=100)
    updated_by: Optional[str] = Field(None, max_length=100)

    @field_validator("company_domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        if "." not in v or len(v.split(".")) < 2 or not v.split(".")[-1]:
            raise ValueError("Domain must contain a valid TLD (e.g. company.com)")
        return v.strip().lower()

class OrganizationConfigCreate(OrganizationConfigBase):
    pass

class OrganizationConfigUpdate(OrganizationConfigBase):
    pass

class OrganizationConfigResponse(OrganizationConfigBase):
    id: str
    version: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
