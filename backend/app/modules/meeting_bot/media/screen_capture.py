from pathlib import Path
import datetime
from playwright.async_api import Page
from loguru import logger
from app.services.storage_service import storage_service

class ScreenCapture:
    async def capture_frame(self, page: Page, session_id: str) -> str:
        """
        Captures screenshot of the active page and saves to disk.
        """
        logger.info("ScreenCapture | Capturing browser page frame...")
        screenshot_dir = storage_service.get_session_dir(session_id) / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        filename = f"frame_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path = screenshot_dir / filename

        # Take screenshot of page
        await page.screenshot(path=str(save_path))
        logger.info(f"ScreenCapture | Screenshot saved: {save_path}")

        # Return relative web accessible path
        return f"sessions/{session_id}/screenshots/{filename}"

screen_capture = ScreenCapture()
