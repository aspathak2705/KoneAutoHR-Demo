import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

class PresentationMemory:
    """
    Stage 3 — Presentation Memory
    Stores runtime state, current slide progress, visited slides, narration history, and timing.
    Deterministic in-memory store without vector DB overhead.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_slide_index: int = 0
        self.total_slides: int = 0
        self.visited_slides: List[int] = []
        self.current_narration: Optional[str] = None
        self.action_history: List[Dict[str, Any]] = []
        self.narration_history: List[Dict[str, Any]] = []
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None
        self.is_paused: bool = False

    def start_session(self, total_slides: int) -> None:
        self.total_slides = total_slides
        self.current_slide_index = 0
        self.visited_slides = []
        self.start_time = datetime.datetime.now()
        self.record_action("START_SESSION", {"total_slides": total_slides})
        logger.info(f"PresentationMemory | Session {self.session_id} started with {total_slides} slides.")

    def record_slide_visit(self, slide_number: int) -> None:
        self.current_slide_index = slide_number
        if slide_number not in self.visited_slides:
            self.visited_slides.append(slide_number)
        self.record_action("SLIDE_VISIT", {"slide_number": slide_number})

    def record_narration(self, slide_number: int, narration_text: str, duration: float) -> None:
        self.current_narration = narration_text
        record = {
            "slide_number": slide_number,
            "text": narration_text,
            "duration": duration,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.narration_history.append(record)
        self.record_action("RECORD_NARRATION", record)

    def record_action(self, action_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.action_history.append({
            "action": action_type,
            "details": details or {},
            "timestamp": datetime.datetime.now().isoformat()
        })

    def complete_session(self) -> None:
        self.end_time = datetime.datetime.now()
        self.record_action("COMPLETE_SESSION", {"visited_count": len(self.visited_slides)})
        logger.info(f"PresentationMemory | Session {self.session_id} completed.")

    def get_progress(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "current_slide": self.current_slide_index + 1 if self.total_slides > 0 else 0,
            "total_slides": self.total_slides,
            "visited_slides": self.visited_slides,
            "percent_complete": round((len(self.visited_slides) / self.total_slides * 100), 1) if self.total_slides > 0 else 0.0,
            "is_paused": self.is_paused
        }
