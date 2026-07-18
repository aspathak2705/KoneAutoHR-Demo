from typing import Dict, List, Callable, Any
from loguru import logger

class RuntimeEventBus:
    def __init__(self):
        # Maps event_name -> list of callback handlers
        self._listeners: Dict[str, List[Callable[[str, Any], None]]] = {}

    def subscribe(self, event_name: str, callback: Callable[[str, Any], None]) -> None:
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
        logger.debug(f"EventBus | Subscribed callback to event: {event_name}")

    def publish(self, session_id: str, event_name: str, data: Any = None) -> None:
        logger.info(f"EventBus | Event: {event_name} | Session: {session_id} | Data: {data}")
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(session_id, data)
                except Exception as e:
                    logger.error(f"EventBus | Error dispatching {event_name} to callback: {e}")

runtime_event_bus = RuntimeEventBus()
