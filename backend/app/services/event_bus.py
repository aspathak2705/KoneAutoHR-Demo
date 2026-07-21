import inspect
from typing import Dict, List, Callable, Any
from app.services.runtime_logger import runtime_logger
from loguru import logger

class RuntimeEventBus:
    def __init__(self):
        # Maps event_name -> list of callback handlers
        self._listeners: Dict[str, List[Callable]] = {}
        
        # Validated list of events for Sprint RC-5
        self.VALID_EVENTS = {
            "MeetingJoined", "MeetingDisconnected", "MeetingLeft", "MeetingEnded",
            "SpeechStarted", "SpeechCompleted", "SpeechInterrupted", "SpeechCancelled",
            "SlideChanged", "QuestionReceived", "QuestionAnswered", "AttendanceUpdated",
            "ReportGenerated", "RuntimeError", "RuntimeRecovered", "ReconnectAttempt", "JoinFailure",
            "MeetingScheduled", "MeetingLaunching"
        }

    def subscribe(self, event_name: str, callback: Callable) -> None:
        if event_name not in self.VALID_EVENTS:
            logger.warning(f"EventBus | Subscribing to non-standard event: {event_name}")
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
        logger.debug(f"EventBus | Subscribed callback to: {event_name}")

    def publish(self, session_id_or_event: str, event_name_or_data: Any = None, data: Any = None) -> None:
        if data is None and (isinstance(event_name_or_data, (str, dict)) or event_name_or_data is None):
            if session_id_or_event in self.VALID_EVENTS:
                event_name = session_id_or_event
                payload = event_name_or_data
                session_id = payload.get("session_id", "global") if isinstance(payload, dict) else "global"
            else:
                session_id = session_id_or_event
                event_name = str(event_name_or_data)
                payload = None
        else:
            session_id = session_id_or_event
            event_name = str(event_name_or_data)
            payload = data

        if event_name not in self.VALID_EVENTS:
            logger.warning(f"EventBus | Publishing non-standard event: {event_name}")
            
        level = "ERROR" if "Error" in event_name or "Failure" in event_name else "INFO"
        runtime_logger.log_event(session_id, event_name, f"Payload: {payload}", level)

        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    sig = inspect.signature(callback)
                    num_params = len(sig.parameters)
                    if num_params == 1:
                        callback(payload)
                    elif num_params == 2:
                        callback(session_id, payload)
                    elif num_params == 3:
                        callback(session_id, event_name, payload)
                    else:
                        callback(payload)
                except Exception as e:
                    logger.error(f"EventBus | Error dispatching {event_name}: {e}")

runtime_event_bus = RuntimeEventBus()
