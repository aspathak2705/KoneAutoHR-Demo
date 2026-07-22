import asyncio
from loguru import logger

class TimingController:
    """
    Manages active transition pauses across slide content, speech events, and quiz prompts.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id

    async def wait_for_transition(self, duration: int) -> None:
        logger.debug(f"TimingController | Standing by for {duration} seconds...")
        await asyncio.sleep(duration)
