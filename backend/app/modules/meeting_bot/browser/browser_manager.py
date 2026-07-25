import os
import json
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright
from app.modules.meeting_bot.browser.browser_session import BrowserSession
from app.modules.meeting_bot.config import meeting_bot_config
from loguru import logger

class BrowserManager:
    """
    LOCKED Architecture: BrowserManager owns ONLY browser resources.
    - Playwright
    - Browser
    - Context
    - Page
    
    No other ownership. RuntimeCoordinator must coordinate.
    """
    def __init__(self):
        self.session: BrowserSession = None
        self.playwright_instance = None

    async def launch(self, session_id: str = "default_session") -> None:
        """
        Launches Playwright Chromium with persistent context to inject user preferences
        and suppress protocol launcher prompts.
        
        Stores the BrowserSession internally.
        Returns None - use self.session to access the session.
        """
<<<<<<< HEAD
        logger.info(f"BrowserManager | Session: {session_id} | Launching persistent Chromium (headless={meeting_bot_config.headless})")

        try:
            logger.info("BrowserManager | Starting async_playwright connection...")
            playwright_instance = await async_playwright().start()
            logger.info("BrowserManager | Playwright engine started successfully.")
        except Exception as e:
            logger.error(f"BrowserManager | Failed to start async_playwright: {e}")
            raise RuntimeError(f"Playwright start failure: {e}") from e

        # Create separate persistent user profile folder per session ID to isolate browser storage
        from app.services.storage_service import storage_service
        temp_dir = storage_service.get_session_dir(session_id) / "profile"
        logger.info(f"BrowserManager | Preparing browser profile data dir: {temp_dir}")
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Write user Preferences JSON directly to bypass Teams app deep link popups
        default_profile_dir = temp_dir / "Default"
        default_profile_dir.mkdir(parents=True, exist_ok=True)
        prefs_path = default_profile_dir / "Preferences"

        prefs_data = {}
        if prefs_path.exists():
            try:
                with open(prefs_path, "r", encoding="utf-8") as f:
                    prefs_data = json.load(f)
                logger.debug("BrowserManager | Existing preferences loaded successfully.")
            except Exception as e:
                logger.warning(f"BrowserManager | Could not load existing preferences: {e}")

        # Inject protocol handler exclusions
        logger.debug("BrowserManager | Writing protocol handler exclusions to profile Preferences...")
        if "protocol_handler" not in prefs_data:
            prefs_data["protocol_handler"] = {}
        if "excluded_schemes" not in prefs_data["protocol_handler"]:
            prefs_data["protocol_handler"]["excluded_schemes"] = {}

        prefs_data["protocol_handler"]["excluded_schemes"]["teams"] = True
        prefs_data["protocol_handler"]["excluded_schemes"]["msteams"] = True
        prefs_data["protocol_handler"]["excluded_schemes"]["ms-word"] = True

        if "profile" not in prefs_data:
            prefs_data["profile"] = {}
        if "default_content_setting_values" not in prefs_data["profile"]:
            prefs_data["profile"]["default_content_setting_values"] = {}
        prefs_data["profile"]["default_content_setting_values"]["notifications"] = 2

        try:
            with open(prefs_path, "w", encoding="utf-8") as f:
                json.dump(prefs_data, f)
            logger.debug("BrowserManager | Preferences JSON updated successfully.")
        except Exception as e:
            logger.error(f"BrowserManager | Failed to save browser Preferences: {e}")

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
            logger.info("BrowserManager | Appending launch args for fake media devices streams.")

        try:
            logger.info("BrowserManager | Triggering playwright launch_persistent_context...")
            context = await playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(temp_dir),
                headless=meeting_bot_config.headless,
                slow_mo=meeting_bot_config.slow_mo,
                args=launch_args,
                viewport={"width": meeting_bot_config.viewport_width, "height": meeting_bot_config.viewport_height},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                permissions=["microphone", "camera"]
            )
            logger.info("BrowserManager | Playwright persistent Chromium launched successfully.")
        except Exception as e:
            logger.exception("BrowserManager | Playwright persistent context launch failed.")
            try:
                await playwright_instance.stop()
            except Exception:
                pass
            raise e

        logger.info("BrowserManager | Resolving initial context page...")
        if len(context.pages) > 0:
            page = context.pages[0]
            logger.debug("BrowserManager | Using existing browser page.")
        else:
            page = await context.new_page()
            logger.debug("BrowserManager | Created new browser page.")

        page._playwright_instance = playwright_instance
        logger.info("BrowserManager | Browser session initialization complete.")

        return BrowserSession(None, context, page)
=======
        logger.info(f"BrowserManager | START launch | Session: {session_id}")
        
        try:
            self.playwright_instance = await async_playwright().start()
            
            # Create separate persistent user profile folder per session ID to isolate browser storage
            from app.services.storage_service import storage_service
            temp_dir = storage_service.get_session_dir(session_id) / "profile"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Write user Preferences JSON directly to bypass Teams app deep link popups
            default_profile_dir = temp_dir / "Default"
            default_profile_dir.mkdir(parents=True, exist_ok=True)
            prefs_path = default_profile_dir / "Preferences"
            
            prefs_data = {}
            if prefs_path.exists():
                try:
                    with open(prefs_path, "r", encoding="utf-8") as f:
                        prefs_data = json.load(f)
                except Exception:
                    pass
                    
            # Inject protocol handler exclusions
            if "protocol_handler" not in prefs_data:
                prefs_data["protocol_handler"] = {}
            if "excluded_schemes" not in prefs_data["protocol_handler"]:
                prefs_data["protocol_handler"]["excluded_schemes"] = {}
                
            prefs_data["protocol_handler"]["excluded_schemes"]["teams"] = True
            prefs_data["protocol_handler"]["excluded_schemes"]["msteams"] = True
            prefs_data["protocol_handler"]["excluded_schemes"]["ms-word"] = True
            
            if "profile" not in prefs_data:
                prefs_data["profile"] = {}
            if "default_content_setting_values" not in prefs_data["profile"]:
                prefs_data["profile"]["default_content_setting_values"] = {}
            prefs_data["profile"]["default_content_setting_values"]["notifications"] = 2
            
            with open(prefs_path, "w", encoding="utf-8") as f:
                json.dump(prefs_data, f)
                
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

            context = await self.playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(temp_dir),
                headless=meeting_bot_config.headless,
                slow_mo=meeting_bot_config.slow_mo,
                args=launch_args,
                viewport={"width": meeting_bot_config.viewport_width, "height": meeting_bot_config.viewport_height},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                permissions=["microphone", "camera"]
            )

            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = await context.new_page()

            self.session = BrowserSession(None, context, page)
            logger.info(f"BrowserManager | SUCCESS launch | Browser ready")
        except Exception as e:
            logger.error(f"BrowserManager | FAILED launch: {e}")
            await self._cleanup_playwright()
            raise

    @property
    def page(self):
        """Returns the current page, or None if not launched."""
        return self.session.page if self.session else None

    @property
    def context(self):
        """Returns the current context, or None if not launched."""
        return self.session.context if self.session else None

    async def close(self) -> None:
        """
        Closes browser resources in order: Page → Context → Browser → Playwright.
        """
        logger.info(f"BrowserManager | START close")
        
        try:
            if self.session:
                await self.session.close()
                self.session = None
            
            await self._cleanup_playwright()
            logger.info(f"BrowserManager | SUCCESS close")
        except Exception as e:
            logger.error(f"BrowserManager | FAILED close: {e}")

    async def _cleanup_playwright(self) -> None:
        """
        Cleans up Playwright instance.
        """
        try:
            if self.playwright_instance:
                await self.playwright_instance.stop()
                self.playwright_instance = None
        except Exception as e:
            logger.error(f"BrowserManager | Failed to stop Playwright: {e}")

>>>>>>> aspathak2705-runtime-lifecycle-refactor

# Singleton instance for legacy code
browser_manager = BrowserManager()
