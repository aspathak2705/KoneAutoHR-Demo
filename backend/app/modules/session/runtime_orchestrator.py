from loguru import logger
from sqlalchemy.orm import Session as DBSession
from app.modules.session.runtime_context import RuntimeContext
from app.modules.browser.browser_supervisor import BrowserSupervisor
from app.modules.presentation.presentation_supervisor import PresentationSupervisor
from app.modules.conversation.conversation_supervisor import ConversationSupervisor
from app.modules.presentation.session_events import session_events

class RuntimeOrchestrator:
    """
    Module 4 — Runtime Orchestrator
    Coordinates BrowserSupervisor, PresentationSupervisor, and ConversationSupervisor
    to prevent god-object designs in supervisor layers.
    """
    def __init__(self, session_id: str):
        self.ctx = RuntimeContext(session_id)
        self.browser_sup = BrowserSupervisor(self.ctx)
        self.pres_sup = PresentationSupervisor(self.ctx)
        self.conv_sup = ConversationSupervisor(self.ctx)

    async def initialize_and_join(self, db: DBSession, teams_url: str, asset_id: str, guest_name: str) -> bool:
        logger.info(f"RuntimeOrchestrator | Starting coordination for session {self.ctx.session_id}...")
        self.ctx.update(meeting_url=teams_url, guest_name=guest_name)
        
        # 1. Start slideshow through Presentation Supervisor
        started = await self.pres_sup.load_and_start(db, asset_id)
        if not started:
            logger.error("RuntimeOrchestrator | Failed to start presentation slideshow.")
            return False

        # 2. Join meeting call through Browser Supervisor
        connected = await self.browser_sup.join_call()
        if connected:
            # 3. Share screen presentation window
            await self.browser_sup.share_screen()
            session_events.publish(self.ctx.session_id, "PresentationShared")
            return True
            
        return False

    async def speak(self, text: str, slide_num: int = 0) -> None:
        await self.conv_sup.speak(text, slide_num)

    async def navigate_slide(self, slide_num: int) -> bool:
        return await self.pres_sup.show_slide(slide_num)

    async def play_video(self, url: str, duration: int) -> None:
        await self.pres_sup.play_video(url, duration)

    async def shutdown(self) -> None:
        logger.info("RuntimeOrchestrator | Executing cleanup sequence across supervisors...")
        await self.browser_sup.stop_sharing()
        await self.browser_sup.leave_call()
        await self.pres_sup.close()
        self.conv_sup.stop_speaking()
