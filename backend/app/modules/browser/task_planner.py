from typing import List, Dict, Any
from loguru import logger

class TaskPlanner:
    """
    Module 7 — Goal / Task Planner
    Decomposes higher-level meeting goals into structured semantic actions.
    """
    def plan_goal(self, goal: str, context_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"TaskPlanner | Decomposing goal: {goal}")
        
        if goal == "JOIN_MEETING":
            # Decomposes into Verify -> Skip Protocol dialog -> Join
            return [
                {"step": "VERIFY_BROWSER", "action": "idle", "reason": "Ensure page context is active."},
                {"step": "SKIP_PROTOCOL_LAUNCHER", "action": "click", "target_text": "Continue on this browser"},
                {"step": "ENTER_GUEST_NAME", "action": "fill_and_join", "reason": "Submit guest name form."}
            ]
            
        elif goal == "SHARE_SCREEN":
            return [
                {"step": "TRIGGER_SHARE_TRAY", "action": "click", "target_text": "share"},
                {"step": "CONFIRM_SHARE", "action": "wait", "duration": 2}
            ]

        # Minimal fallback plan
        return [{"step": "DEFAULT_IDLE", "action": "idle", "reason": "Default planned placeholder step."}]

task_planner = TaskPlanner()
