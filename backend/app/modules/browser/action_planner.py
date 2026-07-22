from typing import Dict, Any, Optional
from loguru import logger

class ActionPlanner:
    """
    Module 3 — Action Planner
    Builds the high-level semantic plan of user commands to execute based on current classified states.
    """
    def plan(self, current_state: str, goal: str, guest_name: str) -> Optional[Dict[str, Any]]:
        if goal == "JOIN_MEETING":
            if current_state == "LANDING":
                return {
                    "action": "click",
                    "target_text": "Continue on this browser",
                    "reason": "Skip application protocol handlers and continue to prejoin web pages."
                }
            elif current_state == "PRE_JOIN":
                return {
                    "action": "fill_and_join",
                    "input_text": guest_name,
                    "target_text": "Join now",
                    "reason": "Enter attendee register name and request meeting roster join."
                }
            elif current_state == "LOBBY":
                return {
                    "action": "wait",
                    "duration": 5,
                    "reason": "Waiting in lobby space to be admitted by the meeting host."
                }
            elif current_state == "MEETING":
                return {
                    "action": "idle",
                    "reason": "Roster connection verified. Indoctor interpretation active."
                }

        logger.warning(f"ActionPlanner | Unplanned path (state: {current_state}, goal: {goal})")
        return None

action_planner = ActionPlanner()
