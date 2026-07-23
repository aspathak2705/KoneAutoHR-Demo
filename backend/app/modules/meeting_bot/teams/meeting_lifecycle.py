from loguru import logger
from app.modules.meeting_bot.bot.bot_state import BotState
from app.modules.meeting_bot.bot.bot_context import MeetingBotContext
from app.modules.meeting_bot.teams.teams_controller import teams_controller

class MeetingLifecycle:
    async def join_meeting(self, context: MeetingBotContext, meeting_url: str, display_name: str) -> None:
        """
        Coordinates Launch -> Open -> Device Selection -> Guest Join.
        """
        logger.info(f"MeetingLifecycle | Joining meeting {meeting_url} as {display_name}")
        context.meeting_url = meeting_url
        context.state = BotState.JOINING

        # 1. Open Meeting URL
        await teams_controller.open_meeting(context.page, meeting_url)
        
        # 2. Toggle mic / camera toggles
        await teams_controller.configure_devices(context.page, mute_mic=True, turn_off_cam=True)

        # 3. Enter Display Name and click Join Now
        await teams_controller.enter_name_and_join(context.page, display_name)
        
        context.state = BotState.CONNECTED
        logger.info("MeetingLifecycle | Bot connected to Teams meeting successfully.")

    async def leave_meeting(self, context: MeetingBotContext) -> None:
        """
        Leaves call and closes browser resources.
        """
        logger.info("MeetingLifecycle | Leaving call...")
        if context.page:
            try:
                await teams_controller.leave_meeting(context.page)
            except Exception:
                pass
        context.state = BotState.DISCONNECTED

meeting_lifecycle = MeetingLifecycle()
