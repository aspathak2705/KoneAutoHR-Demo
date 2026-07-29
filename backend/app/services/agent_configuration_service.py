from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.repositories.agent_configuration_repository import agent_configuration_repository
from app.models.agent_configuration import AgentConfiguration
from app.schemas.agent_configuration import AgentConfigurationUpdate
from app.db.unit_of_work import UnitOfWork

class AgentConfigurationService:
    def get_config(self, db: DBSession) -> Optional[AgentConfiguration]:
        return agent_configuration_repository.get_config(db)

    def update_config(self, db: DBSession, config_in: AgentConfigurationUpdate) -> AgentConfiguration:
        with UnitOfWork(db):
            return agent_configuration_repository.create_or_update(
                db=db,
                provider=config_in.provider,
                email=config_in.email,
                tenant=config_in.tenant,
                profile_path=config_in.profile_path,
                is_connected=config_in.is_connected
            )

    def get_profile_path(self, db: DBSession) -> Optional[str]:
        cfg = self.get_config(db)
        if cfg and cfg.is_connected:
            return cfg.profile_path
        return None

    def get_connection_state(self, db: DBSession) -> bool:
        cfg = self.get_config(db)
        if cfg:
            return cfg.is_connected
        return False

agent_configuration_service = AgentConfigurationService()
