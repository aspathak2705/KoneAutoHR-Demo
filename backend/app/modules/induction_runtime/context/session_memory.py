import time
from typing import List, Dict, Any

class SessionMemory:
    def __init__(self):
        self.current_slide_number: int = 0
        self.slides_completed: List[int] = []
        self.questions_asked: List[Dict[str, Any]] = []
        self.questions_answered: List[Dict[str, Any]] = []
        self.current_topic: str = "Welcome and Greeting"
        self.start_timestamp: float = time.time()

    def record_slide_reached(self, slide_num: int, title: str = "") -> None:
        """
        Updates current slide number and adds it to completion history.
        """
        self.current_slide_number = slide_num
        if slide_num not in self.slides_completed:
            self.slides_completed.append(slide_num)
        if title:
            self.current_topic = title

    def record_question(self, speaker: str, question: str) -> None:
        """
        Records a incoming question from attendee.
        """
        self.questions_asked.append({
            "speaker": speaker,
            "question": question,
            "timestamp": time.time()
        })

    def record_answer(self, question: str, answer: str) -> None:
        """
        Records a generated answer.
        """
        self.questions_answered.append({
            "question": question,
            "answer": answer,
            "timestamp": time.time()
        })

    def get_session_duration(self) -> float:
        """
        Returns elapsed duration in seconds.
        """
        return time.time() - self.start_timestamp

    def get_memory_report(self) -> Dict[str, Any]:
        """
        Assembles current memory summary dict.
        """
        return {
            "current_slide": self.current_slide_number,
            "total_slides_completed": len(self.slides_completed),
            "slides_completed_list": self.slides_completed,
            "questions_asked_count": len(self.questions_asked),
            "questions_answered_count": len(self.questions_answered),
            "current_topic": self.current_topic,
            "elapsed_seconds": self.get_session_duration()
        }
