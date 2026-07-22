from typing import Dict, Any
from loguru import logger

class StateClassifier:
    """
    Module 3 — State Classifier
    Determines current browser page workflow location (Landing, PreJoin, Lobby, Meeting, Error).
    """
    def classify(self, perception: Dict[str, Any]) -> str:
        url = perception.get("url", "")
        title = perception.get("title", "")
        buttons = [b.lower() for b in perception.get("buttons", [])]
        inputs = [i.lower() for i in perception.get("inputs", [])]

        if "launcher" in url or any("continue on this browser" in b for b in buttons):
            return "LANDING"
        
        if "meet" in url or "light-meetings" in url or any("join now" in b for b in buttons) or any("type your name" in i for i in inputs):
            # Check if pre-join page vs. inside the meeting
            if any("camera" in b or "mic" in b or "video" in b or "audio" in b for b in buttons) and any("join now" in b or "join" in b for b in buttons):
                return "PRE_JOIN"
            if any("leave" in b or "hang up" in b or "disconnect" in b or "chat" in b for b in buttons):
                return "MEETING"
            return "LOBBY"

        if "lobby" in url or "waiting" in url:
            return "LOBBY"

        # Safe fallback
        if any("leave" in b or "hang up" in b or "mute" in b for b in buttons):
            return "MEETING"

        logger.debug(f"StateClassifier | Unclassified location state (url: {url}, title: {title})")
        return "UNKNOWN"

state_classifier = StateClassifier()
