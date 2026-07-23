from typing import Callable, Dict, List, Any
from app.modules.induction_runtime.models.session_event import SessionEvent
from loguru import logger

class RuntimeEventBus:
    def __init__(self):
        # Maps event_name -> list of subscriber callbacks
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def subscribe(self, event: SessionEvent, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribes a callable callback to a specific runtime session event.
        """
        event_name = event.value
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)
        logger.debug(f"RuntimeEventBus | Subscribed callback {callback.__name__ if hasattr(callback, '__name__') else callback} to event: {event_name}")

    def publish(self, event: SessionEvent, payload: Dict[str, Any]) -> None:
        """
        Publishes a runtime event payload to all registered subscribers.
        """
        event_name = event.value
        logger.info(f"RuntimeEventBus | Event Published: {event_name} | Payload keys: {list(payload.keys())}")
        
        callbacks = self._subscribers.get(event_name, [])
        for callback in callbacks:
            try:
                callback(payload)
            except Exception as e:
                logger.error(f"RuntimeEventBus | Error dispatching {event_name} to callback {callback}: {e}")

    def clear(self) -> None:
        """
        Clears all subscriptions.
        """
        self._subscribers.clear()

runtime_event_bus = RuntimeEventBus()
