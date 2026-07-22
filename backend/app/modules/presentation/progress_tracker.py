from loguru import logger

class ProgressTracker:
    """
    Tracks and logs slide progression metrics during a session.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._history = []

    def record_slide_presented(self, slide_number: int, duration_seconds: int) -> None:
        self._history.append({
            "slide_number": slide_number,
            "duration_seconds": duration_seconds
        })
        logger.info(f"ProgressTracker | Recorded Slide {slide_number} display duration: {duration_seconds}s")

    def get_progress_summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "total_slides_presented": len(self._history),
            "history": self._history
        }
