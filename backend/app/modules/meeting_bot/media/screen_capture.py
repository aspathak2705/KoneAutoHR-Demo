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

        await page.screenshot(path=str(save_path))
        logger.info(f"ScreenCapture | Screenshot saved: {save_path}")

        return f"sessions/{session_id}/screenshots/{filename}"

    async def capture_step(self, page: Page, session_id: str, step_name: str) -> str:
        """
        Captures screenshot for a named verification step milestone.
        Maps the step_name to a standardized file name with numeric prefixes.
        """
        logger.info(f"ScreenCapture | Capturing milestone step frame: {step_name}")
        screenshot_dir = storage_service.get_session_dir(session_id) / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Milestone step map to centralize names
        step_map = {
            "browser_started": "01_browser_started.png",
            "meeting_loaded": "02_meeting_loaded.png",
            "devices_configured": "03_devices_configured.png",
            "join_requested": "04_join_requested.png",
            "waiting_lobby": "05_waiting_lobby.png",
            "connected": "06_connected.png",
            "before_leave": "07_before_leave.png"
        }

        filename = step_map.get(step_name, f"{step_name}.png")
        save_path = screenshot_dir / filename

        try:
            await page.screenshot(path=str(save_path))
            logger.info(f"ScreenCapture | Milestone screenshot saved: {save_path}")
        except Exception as e:
            logger.error(f"ScreenCapture | Failed to capture milestone frame: {e}")

        return str(save_path)

screen_capture = ScreenCapture()
