from sqlalchemy.orm import Session as DBSession
from typing import Optional
from loguru import logger
import datetime
from app.modules.configuration.configuration_repository import configuration_repository
from app.models.organization_config import OrganizationConfig
from app.schemas.organization_config import OrganizationConfigCreate, OrganizationConfigUpdate

class ConfigurationService:
    def get_active_config(self, db: DBSession) -> Optional[OrganizationConfig]:
        return configuration_repository.get_active(db)

    def save_config(self, db: DBSession, config_in: OrganizationConfigUpdate) -> OrganizationConfig:
        active = configuration_repository.get_active(db)
        if active:
            updated = configuration_repository.update(db, active, config_in)
            logger.info(f"Organization Updated | Company: {updated.company_name} | Timestamp: {datetime.datetime.now()}")
            return updated
        else:
            # Cast Update object to Create object since fields match
            create_in = OrganizationConfigCreate(**config_in.model_dump())
            created = configuration_repository.create(db, create_in)
            logger.info(f"Organization Created | Company: {created.company_name} | Timestamp: {datetime.datetime.now()}")
            return created

configuration_service = ConfigurationService()
