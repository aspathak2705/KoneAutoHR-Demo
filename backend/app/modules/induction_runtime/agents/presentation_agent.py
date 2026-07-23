from typing import Dict, Any
from app.modules.induction.llm.client import llm_client
from app.core.config import settings
from loguru import logger

class PresentationAgent:
    async def format_narration(
        self,
        slide_title: str,
        slide_narration: str,
        presenter: Dict[str, Any]
    ) -> str:
        """
        Adapts standard script slide narration into conversational trainer presentation script.
        """
        trainer_name = presenter.get("ai_trainer_name", "KONE Trainer")
        tone = presenter.get("vocal_tone", "Professional")
        style = presenter.get("communication_style", "Friendly")

        prompt = f"""
        Adapt the following slide narration into a conversational training dialogue.
        Slide Title: {slide_title}
        Raw Narration: {slide_narration}
        Speaker: {trainer_name}
        Vocal Tone: {tone}
        Style: {style}
        
        Respond ONLY in the following JSON format:
        {{
            "conversational_text": "Spoken presentation content"
        }}
        """

        if settings.LLM_API_KEY:
            try:
                res = await llm_client.generate_json(prompt, name="presentation_agent")
                text = res.get("conversational_text")
                if text:
                    logger.info(f"PresentationAgent | Formatted slide '{slide_title}' narration via LLM.")
                    return text
            except Exception as e:
                logger.error(f"PresentationAgent | LLM narration formatting failed: {e}. Falling back to raw text.")

        logger.info(f"PresentationAgent | Using raw slide '{slide_title}' narration text fallback.")
        return slide_narration

presentation_agent = PresentationAgent()
