from app.modules.meeting_bot.bot.bot_context import MeetingBotContext
from app.modules.meeting_bot.bot.bot_state import BotState
from app.modules.meeting_bot.teams.participant_monitor import participant_monitor
from loguru import logger

class HealthMonitor:
    async def evaluate_health(self, context: MeetingBotContext) -> dict:
        """
        Evaluates raw capabilities metrics of the bot session:
        Browser Alive, Meeting Connected, Page Responsive, Bot Running.
        """
        browser_alive = False
        page_alive = False
        meeting_connected = False
        bot_running = context.state != BotState.STOPPED and context.state != BotState.FAILED

        if context.browser:
            try:
                browser_alive = context.browser.is_connected()
            except Exception:
                pass

        if context.page:
            try:
                page_alive = not context.page.is_closed()
            except Exception:
                pass

        if page_alive:
            try:
                meeting_connected = await participant_monitor.meeting_active(context.page)
            except Exception:
                pass

        status = {
            "browser_alive": browser_alive,          # Browser Alive
            "meeting_connected": meeting_connected,  # Meeting Connected
            "page_responsive": page_alive,           # Page Responsive
            "bot_running": bot_running,              # Bot Running
            "is_healthy": browser_alive and page_alive and (context.state == BotState.CONNECTED or context.state == BotState.READY)
        }
        
        logger.debug(f"HealthMonitor | Health check: {status}")
        return status

health_monitor = HealthMonitor()
