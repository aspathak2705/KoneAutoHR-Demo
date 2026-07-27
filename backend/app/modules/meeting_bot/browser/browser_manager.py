import json

from playwright.async_api import async_playwright
from loguru import logger

from app.modules.meeting_bot.browser.browser_session import BrowserSession
from app.modules.meeting_bot.config import meeting_bot_config


class BrowserManager:
    """
    LOCKED Architecture

    BrowserManager owns ONLY browser resources.

    - Playwright
    - Browser Context
    - Page

    RuntimeCoordinator owns lifecycle.
    """

    def __init__(self):
        self.session: BrowserSession | None = None
        self.playwright_instance = None

    async def launch(self, session_id: str = "default_session") -> BrowserSession:
        """
        Launch Playwright persistent Chromium.

        Stores BrowserSession internally.
        """

        logger.info(f"BrowserManager | START launch | Session: {session_id}")

        try:
            self.playwright_instance = await async_playwright().start()

            from app.services.storage_service import storage_service

            temp_dir = storage_service.get_session_dir(session_id) / "profile"
            temp_dir.mkdir(parents=True, exist_ok=True)

            default_profile_dir = temp_dir / "Default"
            default_profile_dir.mkdir(parents=True, exist_ok=True)

            prefs_path = default_profile_dir / "Preferences"

            prefs_data = {}

            if prefs_path.exists():
                try:
                    with open(prefs_path, "r", encoding="utf-8") as f:
                        prefs_data = json.load(f)
                except Exception:
                    logger.warning("Unable to read browser Preferences.")

            prefs_data.setdefault("protocol_handler", {})
            prefs_data["protocol_handler"].setdefault("excluded_schemes", {})

            prefs_data["protocol_handler"]["excluded_schemes"]["teams"] = True
            prefs_data["protocol_handler"]["excluded_schemes"]["msteams"] = True
            prefs_data["protocol_handler"]["excluded_schemes"]["ms-word"] = True

            prefs_data.setdefault("profile", {})
            prefs_data["profile"].setdefault(
                "default_content_setting_values",
                {}
            )

            prefs_data["profile"]["default_content_setting_values"][
                "notifications"
            ] = 2

            with open(prefs_path, "w", encoding="utf-8") as f:
                json.dump(prefs_data, f)

            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]

            if meeting_bot_config.use_fake_devices:
                launch_args.extend(
                    [
                        "--use-fake-ui-for-media-stream",
                        "--use-fake-device-for-media-stream",
                    ]
                )

            context = await self.playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(temp_dir),
                headless=meeting_bot_config.headless,
                slow_mo=meeting_bot_config.slow_mo,
                args=launch_args,
                viewport={
                    "width": meeting_bot_config.viewport_width,
                    "height": meeting_bot_config.viewport_height,
                },
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                permissions=["microphone", "camera"],
            )

            if context.pages:
                page = context.pages[0]
                page._playwright_instance = self.playwright_instance
            else:
                page = await context.new_page()

            self.session = BrowserSession(
                browser=None,
                context=context,
                page=page,
            )

            logger.info("BrowserManager | SUCCESS launch | Browser ready")
            return self.session
        
        except Exception as e:
            logger.exception(f"BrowserManager | FAILED launch: {e}")
            await self._cleanup_playwright()
            raise

    @property
    def page(self):
        """Return current page."""

        return self.session.page if self.session else None

    @property
    def context(self):
        """Return current browser context."""

        return self.session.context if self.session else None

    async def close(self) -> None:
        """
        Close browser resources.
        """

        logger.info("BrowserManager | START close")

        try:
            if self.session:
                await self.session.close()
                self.session = None

            await self._cleanup_playwright()

            logger.info("BrowserManager | SUCCESS close")

        except Exception as e:
            logger.exception(f"BrowserManager | FAILED close: {e}")

    async def _cleanup_playwright(self) -> None:
        """
        Stop Playwright.
        """

        try:
            if self.playwright_instance:
                await self.playwright_instance.stop()
                self.playwright_instance = None

        except Exception as e:
            logger.exception(f"Failed stopping Playwright: {e}")


# Singleton instance for legacy code
browser_manager = BrowserManager()