from typing import Dict, Any
from sqlalchemy.orm import Session as DBSession
from app.models.organization_config import OrganizationConfig
from loguru import logger

class TrainerContextManager:
    def __init__(self):
        self.profile: Dict[str, Any] = {}

    def load_presenter_profile(self, db: DBSession) -> Dict[str, Any]:
        """
        Retrieves KONE company profile and trainer properties from active database configuration.
        """
        config = db.query(OrganizationConfig).first()
        if not config:
            logger.warning("TrainerContextManager | No OrganizationConfig found. Falling back to default profile.")
            self.profile = {
                "company_name": "KONE",
                "company_domain": "kone.com",
                "ai_trainer_name": "KONE AI Trainer",
                "ai_role_description": "AI Onboarding Assistant",
                "vocal_tone": "Professional",
                "communication_style": "Friendly"
            }
        else:
            self.profile = {
                "company_name": config.company_name,
                "company_domain": config.company_domain,
                "ai_trainer_name": config.ai_trainer_name,
                "ai_role_description": config.ai_role_description,
                "vocal_tone": config.vocal_tone,
                "communication_style": config.communication_style
            }
        logger.info(f"TrainerContextManager | Loaded profile: {self.profile['ai_trainer_name']} at {self.profile['company_name']}")
        return self.profile

    def get_trainer_name(self) -> str:
        return self.profile.get("ai_trainer_name", "KONE AI Trainer")

    def get_company_name(self) -> str:
        return self.profile.get("company_name", "KONE")

    def get_profile_summary(self) -> str:
        return f"{self.get_trainer_name()}, representing {self.get_company_name()}"
