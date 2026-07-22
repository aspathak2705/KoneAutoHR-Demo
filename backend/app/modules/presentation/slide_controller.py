from loguru import logger
from app.services.teams_runtime_service import teams_runtime_service

class SlideController:
    """
    Controls slide route navigation and active slide states.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_slide: int = 1

    async def go_to_slide(self, slide_number: int) -> bool:
        self.current_slide = slide_number
        logger.info(f"SlideController | Navigating to slide {slide_number} for session {self.session_id}")
        # Advance slide on active Teams browser control
        return await teams_runtime_service.advance_slide(self.session_id)

    async def next_slide(self) -> bool:
        self.current_slide += 1
        logger.info(f"SlideController | Next slide: {self.current_slide}")
        return await teams_runtime_service.advance_slide(self.session_id)

    async def previous_slide(self) -> bool:
        if self.current_slide > 1:
            self.current_slide -= 1
            logger.info(f"SlideController | Previous slide: {self.current_slide}")
            return True
        return False
