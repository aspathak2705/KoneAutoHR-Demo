from loguru import logger
from app.modules.meeting_bot.bot.bot_state import BotState
from app.modules.meeting_bot.bot.bot_context import MeetingBotContext
from app.modules.meeting_bot.browser.browser_manager import browser_manager
from app.modules.meeting_bot.teams.meeting_lifecycle import meeting_lifecycle
from app.modules.meeting_bot.health_monitor import health_monitor

class MeetingBot:
    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id
        self.context = MeetingBotContext()

    def set_state(self, state: BotState) -> None:
        logger.info(f"MeetingBot | State transitioned: {self.context.state} -> {state}")
        self.context.state = state

    async def initialize(self) -> None:
        """
        Launches Playwright and establishes BrowserSession.
        """
        if self.context.state != BotState.CREATED:
            logger.warning("MeetingBot | Bot already initialized or running.")
            return

        self.set_state(BotState.INITIALIZING)
        try:
            session = await browser_manager.launch(self.session_id)
            self.context.browser = session.browser
            self.context.browser_context = session.context
            self.context.page = session.page
            
            # Retrieve playwright instance
            self.context.playwright = getattr(session.page, "_playwright_instance", None)
            
            self.set_state(BotState.READY)
            logger.info("MeetingBot | Initialization completed successfully. Ready to join meetings.")
        except Exception as e:
            logger.exception("MeetingBot | Initialization failed.")
            self.set_state(BotState.FAILED)
            raise e

    async def join(self, meeting_url: str, display_name: str = "KONE AI Bot") -> None:
        """
        Joins Teams meeting.
        """
        if self.context.state not in [BotState.READY, BotState.DISCONNECTED]:
            raise ValueError(f"MeetingBot | Cannot join meeting from current state: {self.context.state}")

        try:
            await meeting_lifecycle.join_meeting(self.context, meeting_url, display_name)
        except Exception as e:
            logger.exception("MeetingBot | Failed to join Teams meeting.")
            self.set_state(BotState.FAILED)
            raise e

    async def leave(self) -> None:
        """
        Leaves call.
        """
        if self.context.state != BotState.CONNECTED:
            logger.warning("MeetingBot | Not connected to any active call.")
            return

        await meeting_lifecycle.leave_meeting(self.context)

    async def stop(self) -> None:
        """
        Gracefully terminates Playwright browser and loop contexts.
        """
        logger.info("MeetingBot | Shutting down browser session...")
        self.set_state(BotState.STOPPED)

        if self.context.page:
            try:
                await self.context.page.close()
            except Exception:
                pass
        if self.context.browser_context:
            try:
                await self.context.browser_context.close()
            except Exception:
                pass
        if self.context.browser:
            try:
                await self.context.browser.close()
            except Exception:
                pass
        if self.context.playwright:
            try:
                await self.context.playwright.stop()
            except Exception:
                pass

        # Clear references
        self.context.page = None
        self.context.browser_context = None
        self.context.browser = None
        self.context.playwright = None

    async def get_health(self) -> dict:
        return await health_monitor.evaluate_health(self.context)
stream_instance = None
