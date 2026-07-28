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
        self.context.session_id = session_id

    def set_state(self, state: BotState) -> None:
        logger.info(f"MeetingBot | State transitioned: {self.context.state} -> {state}")
        self.context.state = state
        try:
            from app.db.database import SessionLocal
            from app.models.runtime import Runtime
            with SessionLocal() as db:
                runtime = db.query(Runtime).filter(Runtime.session_id == self.session_id).order_by(Runtime.updated_at.desc()).first()
                if not runtime:
                    runtime = Runtime(session_id=self.session_id, state=state.value, current_slide=0)
                    db.add(runtime)
                else:
                    runtime.state = state.value
                db.commit()
                logger.info(f"MeetingBot | Synchronized database state to: {state.value}")
        except Exception as db_err:
            logger.error(f"MeetingBot | Failed to synchronize database state: {db_err}")


    async def initialize(self):

        logger.info("MeetingBot.initialize() ENTER")
        
        if self.context.page is None:
            raise RuntimeError(
                "MeetingBot requires RuntimeCoordinator to inject browser resources."
            )

        logger.info("MeetingBot.initialize() setting state READY")

        self.set_state(BotState.READY)

        logger.info(
            f"MeetingBot.initialize() END | state={self.context.state}"
        )


    async def join(self, meeting_url: str, display_name: str = "KONE AI Bot") -> None:
        """
        Joins Teams meeting.
        """
        if self.context.state == BotState.CREATED:
            raise RuntimeError(
                "MeetingBot has not been initialized by RuntimeCoordinator."
        )

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
