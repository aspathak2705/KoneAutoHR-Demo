from loguru import logger
from app.modules.session.runtime_context import RuntimeContext

class DecisionEngine:
    """
    Module 11 — Decision Engine
    Evaluates context state and answers architectural queries: should retry, recover, continue, or ask HR.
    """
    def evaluate_next_step(self, ctx: RuntimeContext, retry_count: int) -> str:
        # State machine decisions
        browser_state = ctx.browser_state.upper()
        current_goal = ctx.current_goal.upper()

        if browser_state == "DISCONNECTED" and current_goal == "JOIN_MEETING":
            if retry_count < 3:
                logger.info("DecisionEngine | Browser disconnected during join. Decision: RETRY.")
                return "RETRY"
            else:
                logger.error("DecisionEngine | Max retries reached. Decision: RECOVER.")
                return "RECOVER"

        if browser_state == "LOBBY":
            logger.info("DecisionEngine | In Lobby waiting admission. Decision: WAIT.")
            return "WAIT"

        if browser_state == "CONNECTED" and current_goal == "JOIN_MEETING":
            logger.info("DecisionEngine | Meeting joined successfully. Decision: CONTINUE.")
            return "CONTINUE"

        # Safe fallback
        return "CONTINUE"

decision_engine = DecisionEngine()
