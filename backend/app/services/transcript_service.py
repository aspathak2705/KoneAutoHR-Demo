from sqlalchemy.orm import Session as DBSession
from app.models.runtime_message import RuntimeMessage
from typing import List, Dict, Any

class TranscriptService:
    def get_chronological_transcript(self, db: DBSession, session_id: str) -> List[Dict[str, Any]]:
        """
        Sprint RC-4: Retrieves dialogue logs combining narration steps, employee questions,
        and AI answers sorted sequentially in chronological order.
        """
        messages = db.query(RuntimeMessage).filter(RuntimeMessage.session_id == session_id).order_by(RuntimeMessage.timestamp.asc()).all()
        return [
            {
                "speaker": m.speaker_name,
                "message_text": m.message_text,
                "timestamp": m.timestamp.isoformat()
            }
            for m in messages
        ]

transcript_service = TranscriptService()
