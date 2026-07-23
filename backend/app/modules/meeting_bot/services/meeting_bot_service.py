from typing import Optional, List, Dict, Any
from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.meeting_bot.bot.bot_state import BotState
from app.modules.meeting_bot.teams.participant_monitor import participant_monitor
from app.modules.meeting_bot.media.chat_monitor import chat_monitor
from app.modules.meeting_bot.media.screen_capture import screen_capture
from app.modules.meeting_bot.media.audio_controller import audio_controller
from app.modules.meeting_bot.desktop.desktop_controller import desktop_controller
from loguru import logger

class MeetingBotService:
    def __init__(self):
        self._bot: Optional[MeetingBot] = None

    def get_bot(self) -> MeetingBot:
        """
        Retrieves or creates the active singleton bot instance.
        """
        if not self._bot:
            self._bot = MeetingBot()
        return self._bot

    async def start_bot(self) -> dict:
        bot = self.get_bot()
        await bot.initialize()
        return {"status": "success", "state": bot.context.state.value}

    async def join_meeting(self, meeting_url: str, display_name: str) -> dict:
        bot = self.get_bot()
        await bot.join(meeting_url, display_name)
        return {"status": "success", "state": bot.context.state.value}

    async def leave_meeting(self) -> dict:
        bot = self.get_bot()
        await bot.leave()
        return {"status": "success", "state": bot.context.state.value}

    async def stop_bot(self) -> dict:
        if self._bot:
            await self._bot.stop()
            self._bot = None
        return {"status": "success", "state": "STOPPED"}

    async def capture_screen(self, session_id: str) -> dict:
        bot = self.get_bot()
        if not bot.context.page:
            raise ValueError("MeetingBot | Browser page is not initialized.")
        path = await screen_capture.capture_frame(bot.context.page, session_id)
        bot.context.last_screenshot_path = path
        return {"status": "success", "screenshot_path": path}

    async def play_audio(self, audio_path: str) -> dict:
        audio_controller.play_audio(audio_path)
        bot = self.get_bot()
        bot.context.audio_state = {"playing": True, "track": audio_path}
        return {"status": "success", "audio_state": bot.context.audio_state}

    async def stop_audio(self) -> dict:
        audio_controller.stop_audio()
        bot = self.get_bot()
        bot.context.audio_state = {"playing": False, "track": None}
        return {"status": "success", "audio_state": bot.context.audio_state}

    async def get_status(self) -> dict:
        bot = self.get_bot()
        health = await bot.get_health()
        return {
            "state": bot.context.state.value,
            "meeting_url": bot.context.meeting_url,
            "health": health,
            "audio_state": bot.context.audio_state,
            "last_screenshot_path": bot.context.last_screenshot_path
        }

    async def get_participants(self) -> dict:
        bot = self.get_bot()
        if bot.context.page:
            names = await participant_monitor.get_participants(bot.context.page)
            bot.context.participants = names
        return {
            "count": len(bot.context.participants),
            "participants": bot.context.participants
        }

    async def get_chat(self) -> dict:
        bot = self.get_bot()
        if bot.context.page:
            messages = await chat_monitor.get_messages(bot.context.page)
            bot.context.chat_messages = messages
        return {
            "messages": bot.context.chat_messages
        }

    def get_desktop_controller(self):
        return desktop_controller

meeting_bot_service = MeetingBotService()
