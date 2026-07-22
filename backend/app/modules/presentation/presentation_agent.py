from typing import Dict, Any, Optional, Tuple
from loguru import logger
from app.modules.presentation.models import SlideData, NarrationBlock, PresentationAction
from app.modules.presentation.narration_engine import narration_engine
from app.modules.induction.llm.client import llm_client

class PresentationAgent:
    """
    Stage 4 — Presentation Agent
    AI presentation intelligence module.
    Understands slide context, evaluates presentation progress, and determines next PresentationAction.
    Never interacts directly with DOM selectors or browser automation.
    """
    def generate_greeting_and_intro(self, company_name: str = "KONE", presenter_name: str = "KONE AutoHR Trainer") -> str:
        """
        Generates dynamic spoken greeting using company context and presenter profile via LLMClient.
        """
        prompt = f"Generate a warm, 2-sentence professional spoken greeting for a company induction at {company_name} presented by digital HR trainer {presenter_name}."
        try:
            greeting = llm_client.generate(prompt)
            if greeting and len(greeting.strip()) > 10:
                return greeting.strip()
        except Exception as e:
            logger.warning(f"PresentationAgent | Greeting LLM generation notice: {e}")
        return f"Hello everyone! Welcome to today's {company_name} induction session. I am {presenter_name}, your digital HR trainer."

    def generate_slide_presentation(
        self,
        slide: SlideData,
        current_index: int,
        total_slides: int,
        company_name: str = "KONE"
    ) -> Tuple[NarrationBlock, PresentationAction]:
        """
        Generates spoken narration for the current slide and decides next presentation action.
        """
        logger.info(f"PresentationAgent | Processing Slide {slide.slide_number} ({current_index + 1}/{total_slides})")
        narration = narration_engine.generate_narration(slide, company_name=company_name)

        if current_index + 1 >= total_slides:
            next_action = PresentationAction(action="COMPLETE", reason="Reached final slide of induction deck.")
        else:
            next_action = PresentationAction(action="ADVANCE_SLIDE", reason="Slide narration complete. Ready for next slide.")

        return narration, next_action

presentation_agent = PresentationAgent()
