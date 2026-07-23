from loguru import logger
from app.modules.meeting_bot.bot.bot_state import BotState
from app.modules.meeting_bot.bot.bot_context import MeetingBotContext
from app.modules.meeting_bot.teams.teams_controller import teams_controller
from app.modules.meeting_bot.teams.participant_monitor import participant_monitor
from app.modules.meeting_bot.media.screen_capture import screen_capture
from app.modules.meeting_bot.config import meeting_bot_config
import asyncio

class MeetingLifecycle:
    async def join_meeting(self, context: MeetingBotContext, meeting_url: str, display_name: str) -> None:
        """
        Coordinates Launch -> Open -> Device Selection -> Guest Join -> Waiting.
        Encapsulates full lobby wait loops from config.py.
        """
        logger.info(f"MeetingLifecycle | Joining meeting {meeting_url} as {display_name}")
        context.meeting_url = meeting_url
        context.state = BotState.JOINING

        # 1. Open Meeting URL (Milestone 02 captured inside teams_controller)
        await teams_controller.open_meeting(context.page, meeting_url)
        
        # 2. Toggle mic / camera toggles (Milestone 03 captured inside teams_controller)
        device_result = await teams_controller.configure_devices(context.page, mute_mic=True, turn_off_cam=True)
        context.metadata = getattr(context, "metadata", {}) or {}
        context.metadata["device_configuration"] = device_result

        # 3. Enter Display Name and click Join Now (Milestone 04 captured inside teams_controller)
        await teams_controller.enter_name_and_join(context.page, display_name)
        
        context.state = BotState.WAITING
        logger.info("MeetingLifecycle | Bot submitted guest request. Waiting in lobby...")
        
        # Capture 05_waiting_lobby
        await screen_capture.capture_step(context.page, "verification_session", "05_waiting_lobby")

        # Poll active status dynamically based on config
        if meeting_bot_config.lobby_wait_enabled:
            attempt = 0
            max_attempts = meeting_bot_config.max_lobby_timeout
            interval = meeting_bot_config.polling_interval
            
            while True:
                if await participant_monitor.meeting_active(context.page):
                    context.state = BotState.CONNECTED
                    logger.info("MeetingLifecycle | Bot connected to Teams meeting successfully (Admitted).")
                    
                    # Capture 06_connected
                    await screen_capture.capture_step(context.page, "verification_session", "06_connected")
                    break
                
                # Check timeouts
                if max_attempts is not None and max_attempts > 0 and attempt >= max_attempts:
                    context.state = BotState.FAILED
                    logger.error("MeetingLifecycle | Lobby wait timeout exceeded. Bot failed to join.")
                    break
                    
                attempt += interval
                await asyncio.sleep(interval)
        else:
            context.state = BotState.CONNECTED
            # Capture 06_connected
            await screen_capture.capture_step(context.page, "verification_session", "06_connected")

    async def leave_meeting(self, context: MeetingBotContext) -> None:
        """
        Leaves call and closes browser resources.
        """
        logger.info("MeetingLifecycle | Leaving call...")
        
        # Capture 07_before_leave right before hangup
        if context.page:
            await screen_capture.capture_step(context.page, "verification_session", "07_before_leave")
            try:
                await teams_controller.leave_meeting(context.page)
            except Exception:
                pass
        context.state = BotState.DISCONNECTED

meeting_lifecycle = MeetingLifecycle()
