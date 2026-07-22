from typing import Dict, Any, Optional
from loguru import logger
from app.services.event_bus import runtime_event_bus

class SessionEvents:
    """
    Sprint 12 — Event System
    Publishes session-centric lifecycle events to runtime EventBus.
    """
    @staticmethod
    def publish(session_id: str, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        payload = {"session_id": session_id, **(details or {})}
        logger.info(f"SessionEvents | [{event_type}] Payload: {payload}")
        runtime_event_bus.publish(session_id, event_type, payload)

session_events = SessionEvents()
