from typing import Dict, List, Callable, Any
from app.services.runtime_logger import runtime_logger
from loguru import logger

class RuntimeEventBus:
    def __init__(self):
        # Maps event_name -> list of callback handlers
        self._listeners: Dict[str, List[Callable[[str, Any], None]]] = {}
        
        # Validated list of events for Sprint RC-5
        self.VALID_EVENTS = {
            "MeetingJoined", "MeetingDisconnected", "MeetingLeft", "MeetingEnded",
            "SpeechStarted", "SpeechCompleted", "SpeechInterrupted", "SpeechCancelled",
            "SlideChanged", "QuestionReceived", "QuestionAnswered", "AttendanceUpdated",
            "ReportGenerated", "RuntimeError", "RuntimeRecovered", "ReconnectAttempt", "JoinFailure"
        }

    def subscribe(self, event_name: str, callback: Callable[[str, Any], None]) -> None:
        if event_name not in self.VALID_EVENTS:
            logger.warning(f"EventBus | Subscribing to non-standard event: {event_name}")
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
        logger.debug(f"EventBus | Subscribed callback to: {event_name}")

    def publish(self, session_id: str, event_name: str, data: Any = None) -> None:
        # Check event safety
        if event_name not in self.VALID_EVENTS:
            logger.warning(f"EventBus | Publishing non-standard event: {event_name}")
            
        # Standardize runtime logging mapping
        level = "ERROR" if "Error" in event_name or "Failure" in event_name else "INFO"
        runtime_logger.log_event(session_id, event_name, f"Payload: {data}", level)

        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(session_id, data)
                except Exception as e:
                    logger.error(f"EventBus | Error dispatching {event_name}: {e}")

runtime_event_bus = RuntimeEventBus()
