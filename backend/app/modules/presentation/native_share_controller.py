import asyncio
from loguru import logger

from app.modules.meeting_bot.desktop.desktop_controller import desktop_controller


class NativeShareController:
    """Owns the native Windows share-picker interaction for a Teams share flow."""

    def __init__(self, desktop_controller_instance=None):
        self.desktop_controller = desktop_controller_instance or desktop_controller

    async def activate_picker(self) -> None:
        logger.info("NativeShareController | Activating native share picker")
        await asyncio.to_thread(self._activate_picker)

    async def click_window_tab(self) -> None:
        logger.info("NativeShareController | Switching to Window tab")
        await asyncio.to_thread(self._click_window_tab)

    async def select_window(self, window_name: str = "PowerPoint Slide Show", *, presentation_name: str | None = None) -> None:
        if presentation_name:
            logger.info(
                f"NativeShareController | Selecting window target: {window_name} (presentation: {presentation_name})"
            )
        else:
            logger.info(f"NativeShareController | Selecting window target: {window_name}")
        await asyncio.sleep(0.25)

    async def click_share(self) -> None:
        logger.info("NativeShareController | Confirming native share selection")
        await asyncio.sleep(0.25)

    def _activate_picker(self) -> None:
        pass

    def _click_window_tab(self) -> None:
        pass
