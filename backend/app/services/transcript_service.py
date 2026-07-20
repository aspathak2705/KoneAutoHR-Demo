import datetime
from sqlalchemy.orm import Session as DBSession
from app.models.runtime_message import RuntimeMessage
from app.models.runtime import Runtime
from typing import List, Dict, Any

class TranscriptService:
    def get_chronological_transcript(self, db: DBSession, session_id: str) -> List[Dict[str, Any]]:
        """
        Sprint RC-4: Assembles chronological dialogue logs combining:
        - AI Narration
        - Employee Speech (STT)
        - AI Responses
        - Runtime Connection Events
        """
        # 1. Fetch conversations
        messages = db.query(RuntimeMessage).filter(RuntimeMessage.session_id == session_id).all()
        transcript_entries = []
        for m in messages:
            transcript_entries.append({
                "timestamp": m.timestamp,
                "speaker": m.speaker_name,
                "message_text": m.message_text,
                "type": "dialogue"
            })

        # 2. Interleave Runtime Events (connection start, drops, transitions)
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if runtime:
            if runtime.started_at:
                transcript_entries.append({
                    "timestamp": runtime.started_at,
                    "speaker": "SYSTEM",
                    "message_text": f"Meeting runtime initiated. Integration state: {runtime.state}",
                    "type": "event"
                })
            if runtime.reconnect_count > 0:
                transcript_entries.append({
                    "timestamp": runtime.updated_at,
                    "speaker": "SYSTEM",
                    "message_text": f"Connection lost. Reconnection count incremented: {runtime.reconnect_count}",
                    "type": "event"
                })

        # Sort chronologically by timestamp
        transcript_entries.sort(key=lambda x: x["timestamp"])

        # Format timestamps to string indices
        return [
            {
                "timestamp": item["timestamp"].isoformat(),
                "speaker": item["speaker"],
                "message_text": item["message_text"],
                "type": item["type"]
            }
            for item in transcript_entries
        ]

transcript_service = TranscriptService()
