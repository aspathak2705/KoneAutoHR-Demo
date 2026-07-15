from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.models.organization_config import OrganizationConfig
from app.schemas.organization_config import OrganizationConfigCreate, OrganizationConfigUpdate

class ConfigurationRepository:
    def get_active(self, db: DBSession) -> Optional[OrganizationConfig]:
        stmt = select(OrganizationConfig).order_by(OrganizationConfig.created_at.asc())
        return db.scalars(stmt).first()

    def create(self, db: DBSession, obj_in: OrganizationConfigCreate) -> OrganizationConfig:
        db_obj = OrganizationConfig(
            company_name=obj_in.company_name,
            company_domain=obj_in.company_domain,
            ai_officer_name=obj_in.ai_officer_name,
            ai_trainer_name=obj_in.ai_trainer_name,
            ai_role_description=obj_in.ai_role_description,
            vocal_tone=obj_in.vocal_tone,
            communication_style=obj_in.communication_style,
            updated_by=obj_in.updated_by,
            version=1
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: DBSession, db_obj: OrganizationConfig, obj_in: OrganizationConfigUpdate) -> OrganizationConfig:
        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_obj, key, value)
        db_obj.version = (db_obj.version or 1) + 1
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete_all(self, db: DBSession) -> None:
        db.query(OrganizationConfig).delete()
        db.commit()

configuration_repository = ConfigurationRepository()
