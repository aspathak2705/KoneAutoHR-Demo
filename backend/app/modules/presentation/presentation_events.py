from typing import Dict, Any, Optional
from loguru import logger
from app.services.event_bus import runtime_event_bus

class PresentationEvents:
    """
    Stage 10 — Event System
    Publishes presentation lifecycle events to the runtime EventBus.
    """
    @staticmethod
    def publish_presentation_started(session_id: str, total_slides: int) -> None:
        payload = {"session_id": session_id, "total_slides": total_slides}
        logger.info(f"PresentationEvents | [PresentationStarted] Payload: {payload}")
        runtime_event_bus.publish(session_id, "PresentationStarted", payload)

    @staticmethod
    def publish_slide_started(session_id: str, slide_number: int, title: str) -> None:
        payload = {"session_id": session_id, "slide_number": slide_number, "title": title}
        logger.info(f"PresentationEvents | [SlideStarted] Payload: {payload}")
        runtime_event_bus.publish(session_id, "SlideStarted", payload)

    @staticmethod
    def publish_narration_started(session_id: str, slide_number: int, text: str) -> None:
        payload = {"session_id": session_id, "slide_number": slide_number, "narration": text[:60]}
        logger.info(f"PresentationEvents | [NarrationStarted] Payload: {payload}")
        runtime_event_bus.publish(session_id, "NarrationStarted", payload)

    @staticmethod
    def publish_narration_completed(session_id: str, slide_number: int) -> None:
        payload = {"session_id": session_id, "slide_number": slide_number}
        logger.info(f"PresentationEvents | [NarrationCompleted] Payload: {payload}")
        runtime_event_bus.publish(session_id, "NarrationCompleted", payload)

    @staticmethod
    def publish_slide_completed(session_id: str, slide_number: int) -> None:
        payload = {"session_id": session_id, "slide_number": slide_number}
        logger.info(f"PresentationEvents | [SlideCompleted] Payload: {payload}")
        runtime_event_bus.publish(session_id, "SlideCompleted", payload)

    @staticmethod
    def publish_presentation_completed(session_id: str, visited_slides_count: int) -> None:
        payload = {"session_id": session_id, "visited_slides_count": visited_slides_count}
        logger.info(f"PresentationEvents | [PresentationCompleted] Payload: {payload}")
        runtime_event_bus.publish(session_id, "PresentationCompleted", payload)

presentation_events = PresentationEvents()
