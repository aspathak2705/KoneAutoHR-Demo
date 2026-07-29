from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.models.agent_configuration import AgentConfiguration

class AgentConfigurationRepository:
    def get_config(self, db: DBSession) -> Optional[AgentConfiguration]:
        stmt = select(AgentConfiguration).order_by(AgentConfiguration.created_at.desc())
        return db.scalars(stmt).first()

    def create_or_update(
        self,
        db: DBSession,
        provider: str = "microsoft",
        email: Optional[str] = None,
        tenant: Optional[str] = None,
        profile_path: Optional[str] = None,
        is_connected: bool = False
    ) -> AgentConfiguration:
        db_obj = self.get_config(db)
        if not db_obj:
            db_obj = AgentConfiguration(
                provider=provider,
                email=email,
                tenant=tenant,
                profile_path=profile_path,
                is_connected=is_connected
            )
            db.add(db_obj)
        else:
            db_obj.provider = provider
            if email is not None:
                db_obj.email = email
            if tenant is not None:
                db_obj.tenant = tenant
            if profile_path is not None:
                db_obj.profile_path = profile_path
            db_obj.is_connected = is_connected
            db.add(db_obj)
        db.flush()
        return db_obj

agent_configuration_repository = AgentConfigurationRepository()
