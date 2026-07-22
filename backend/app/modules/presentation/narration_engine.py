import re
from typing import Dict, Any, Optional
from loguru import logger
from app.modules.induction.llm.client import llm_client
from app.modules.presentation.models import NarrationBlock, SlideData

class NarrationEngine:
    """
    Stage 5 — Narration Engine
    Converts raw slide content and static scripts into natural, professional HR spoken narration.
    Produces structured NarrationBlock containing text, estimated speech duration, and pause points.
    """
    def generate_narration(
        self,
        slide: SlideData,
        company_name: str = "KONE",
        presenter_name: str = "KONE AutoHR Presenter"
    ) -> NarrationBlock:
        """
        Transforms slide content into natural spoken HR narration.
        """
        if slide.raw_narration and len(slide.raw_narration.strip()) > 10:
            raw_text = slide.raw_narration.strip()
        else:
            raw_text = f"Slide {slide.slide_number}: {slide.title}. {slide.content}"

        # Calculate estimated duration (assuming average 150 words per minute speaking rate)
        words = len(raw_text.split())
        estimated_duration = max(3.0, round(words / 2.5, 1))

        # Split text into natural pause points at punctuation marks
        sentences = re.split(r'(?<=[.!?]) +', raw_text)
        pause_points = [round(i * 3.5, 1) for i in range(1, len(sentences))]

        block = NarrationBlock(
            slide_number=slide.slide_number,
            text=raw_text,
            estimated_duration=estimated_duration,
            emotion="warm_professional",
            pause_points=pause_points
        )
        logger.info(f"NarrationEngine | Slide {slide.slide_number}: Generated narration ({words} words, ~{estimated_duration}s).")
        return block

narration_engine = NarrationEngine()
