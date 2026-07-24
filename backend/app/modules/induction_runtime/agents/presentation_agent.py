from typing import Dict, Any
from loguru import logger

class PresentationAgent:
    async def format_narration(
        self,
        slide_title: str,
        slide_narration: str,
        presenter: Dict[str, Any]
    ) -> str:
        """
        Loads slide narration script directly and returns it without any LLM modifications.
        Guarantees exact consistency with prepared scripts.
        """
        trainer_name = presenter.get("ai_trainer_name", "KONE Trainer")
        company = presenter.get("company_name", "KONE")

        # Replace standard template placeholder variables if present
        spoken_text = slide_narration.replace("{trainer_name}", trainer_name).replace("{company_name}", company)
        
        logger.info(f"PresentationAgent | Loaded direct narration text for slide '{slide_title}'.")
        return spoken_text

presentation_agent = PresentationAgent()
