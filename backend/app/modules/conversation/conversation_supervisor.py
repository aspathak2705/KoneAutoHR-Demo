from loguru import logger
from app.modules.session.runtime_context import RuntimeContext
from app.modules.presentation.speech_engine import speech_engine
from app.modules.presentation.models import NarrationBlock

class ConversationSupervisor:
    """
    Supervises voice narration queues, audio status, and user audio interrupt events.
    """
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    async def speak(self, text: str, slide_num: int = 0) -> None:
        if not text:
            return
        logger.info(f"ConversationSupervisor | Speaking: '{text}'")
        self.ctx.update(is_speaking=True, active_narration=text)
        
        words = len(text.split())
        duration = max(2.0, round(words / 2.5, 1))
        
        await speech_engine.speak(NarrationBlock(
            slide_number=slide_num,
            text=text,
            estimated_duration=duration
        ))
        
        self.ctx.update(is_speaking=False, active_narration="")

    def stop_speaking(self) -> None:
        speech_engine.stop()
        self.ctx.update(is_speaking=False, active_narration="")
        logger.info("ConversationSupervisor | Stopped voice output.")
