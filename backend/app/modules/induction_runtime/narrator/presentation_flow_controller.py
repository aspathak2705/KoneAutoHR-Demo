from typing import Dict, Any, List, Optional
from app.modules.induction_runtime.narrator.voice_output_interface import VoiceOutputInterface
from loguru import logger

class PresentationFlowController:
    def __init__(self, voice_output: VoiceOutputInterface):
        self.voice_output = voice_output
        self.slides_script: List[Dict[str, Any]] = []
        self.current_slide_idx: int = 0
        self.narration_completed_callback: Optional[Any] = None

    def load_presentation_script(self, script_slides: List[Dict[str, Any]]) -> None:
        """
        Loads slide narration metadata array.
        """
        self.slides_script = sorted(script_slides, key=lambda x: x.get("slide_number", 0))
        self.current_slide_idx = 0
        logger.info(f"PresentationFlowController | Loaded {len(self.slides_script)} slide narration segments.")

    def get_slide_by_number(self, slide_num: int) -> Optional[Dict[str, Any]]:
        """
        Finds slide entry by slide number.
        """
        for slide in self.slides_script:
            if slide.get("slide_number") == slide_num:
                return slide
        return None

    def trigger_slide_narration(self, slide_num: int, completion_callback: Optional[Any] = None) -> bool:
        """
        Fetches slide script and speaks the narration segment.
        """
        slide = self.get_slide_by_number(slide_num)
        if not slide:
            logger.warning(f"PresentationFlowController | No narration script found for slide number: {slide_num}")
            return False

        narration = slide.get("narration", "")
        if not narration:
            logger.warning(f"PresentationFlowController | Empty narration text on slide {slide_num}")
            return False

        logger.info(f"PresentationFlowController | Triggering narration playback for Slide {slide_num}")
        self.voice_output.say(narration, completion_callback)
        return True
