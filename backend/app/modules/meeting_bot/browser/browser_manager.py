import os
from playwright.async_api import async_playwright
from app.modules.meeting_bot.browser.browser_session import BrowserSession
from app.modules.meeting_bot.config import meeting_bot_config
from loguru import logger

class BrowserManager:
    async def launch(self) -> BrowserSession:
        """
        Launches Playwright Chromium with settings-defined parameters from config.py.
        """
        logger.info(f"BrowserManager | Launching Chromium (headless={meeting_bot_config.headless}, slow_mo={meeting_bot_config.slow_mo}ms)")
        
        playwright_instance = await async_playwright().start()
        
        # Configure browser options
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled"
        ]
        
        if meeting_bot_config.use_fake_devices:
            launch_args.extend([
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream"
            ])

        browser = await playwright_instance.chromium.launch(
            headless=meeting_bot_config.headless,
            slow_mo=meeting_bot_config.slow_mo,
            args=launch_args
        )

        context = await browser.new_context(
            viewport={"width": meeting_bot_config.viewport_width, "height": meeting_bot_config.viewport_height},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            permissions=["microphone", "camera"]
        )

        page = await context.new_page()
        page._playwright_instance = playwright_instance

        return BrowserSession(browser, context, page)

browser_manager = BrowserManager()
