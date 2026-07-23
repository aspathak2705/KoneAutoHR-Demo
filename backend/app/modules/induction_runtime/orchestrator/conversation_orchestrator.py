from app.modules.induction_runtime.models.runtime_state import RuntimeState
from loguru import logger

class ConversationOrchestrator:
    def determine_next_speaker(self, state: RuntimeState) -> str:
        """
        Determines which agent should speak next based on the session state.
        """
        if state == RuntimeState.INTRODUCTION:
            speaker = "GreetingAgent"
        elif state == RuntimeState.PRESENTING:
            speaker = "PresentationAgent"
        elif state == RuntimeState.QUESTION_ANSWER:
            speaker = "QAAgent"
        elif state == RuntimeState.COMPLETED:
            speaker = "ClosingAgent"
        else:
            speaker = "System"
            
        logger.debug(f"ConversationOrchestrator | Resolved active speaker for state {state.value} -> {speaker}")
        return speaker
