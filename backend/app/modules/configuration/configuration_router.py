from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db
from app.schemas.organization_config import OrganizationConfigResponse, OrganizationConfigUpdate
from app.modules.configuration.configuration_service import configuration_service

router = APIRouter(prefix="/configuration", tags=["Organization Configuration"])

@router.get("", response_model=OrganizationConfigResponse)
def get_configuration(db: DBSession = Depends(get_db)):
    config = configuration_service.get_active_config(db)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization configuration not found"
        )
    return config

@router.put("", response_model=OrganizationConfigResponse)
def save_configuration(payload: OrganizationConfigUpdate, db: DBSession = Depends(get_db)):
    try:
        return configuration_service.save_config(db, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


