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
    Tracks browser sessions and playwright instances indexed by session_id.
    """

    def __init__(self):
        self._sessions: dict[str, BrowserSession] = {}
        self._playwright_instances: dict[str, any] = {}
        # Tracks active profile directory ownership: canonical_path_str -> session_id
        self._profile_owners: dict[str, str] = {}
        # Backward compatibility properties pointing to last active session
        self.session: BrowserSession | None = None
        self.playwright_instance = None

    def get_session(self, session_id: str = "default_session") -> BrowserSession | None:
        """Retrieve browser session for a specific session_id. Returns strictly the requested session or None."""
        return self._sessions.get(session_id)

    def get_page(self, session_id: str = "default_session"):
        sess = self.get_session(session_id)
        return sess.page if sess else None

    def get_context(self, session_id: str = "default_session"):
        sess = self.get_session(session_id)
        return sess.context if sess else None

    async def launch(self, session_id: str = "default_session") -> BrowserSession:
        """
        Launch Playwright persistent Chromium.

        Stores BrowserSession internally indexed by session_id.
        """

        logger.info(f"BrowserManager | START launch | Session: {session_id}")

        try:
            pw_instance = await async_playwright().start()
            self._playwright_instances[session_id] = pw_instance
            self.playwright_instance = pw_instance

            from app.core.config import settings
            from app.db.database import SessionLocal
            from app.services.agent_configuration_service import agent_configuration_service
            from pathlib import Path
            
            custom_profile = None
            with SessionLocal() as db:
                custom_profile = agent_configuration_service.get_profile_path(db)

            if custom_profile:
                temp_dir = Path(custom_profile)
                logger.info(f"BrowserManager | Launching with custom authenticated Edge profile: {temp_dir}")
            else:
                temp_dir = Path(settings.BROWSER_PROFILE_DIR) / "msedge"
                logger.info(f"BrowserManager | Launching with default Edge profile: {temp_dir}")
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Check profile ownership to prevent Windows file locking contention (EBUSY)
            canonical_profile = str(temp_dir.resolve()).lower()
            current_owner = self._profile_owners.get(canonical_profile)
            if current_owner and current_owner != session_id:
                # Check if current owner session is still genuinely active
                owner_session = self._sessions.get(current_owner)
                if owner_session and owner_session.page and not owner_session.page.is_closed():
                    msg = (
                        f"Edge profile directory '{temp_dir}' is currently in use by active session '{current_owner}'. "
                        f"Concurrent sessions sharing the same Windows browser profile are locked."
                    )
                    logger.warning(f"BrowserManager | Profile contention: {msg}")
                    raise RuntimeError(msg)
                else:
                    logger.info(
                        f"BrowserManager | Clearing stale profile ownership for '{current_owner}' on '{temp_dir}'."
                    )
                    self._profile_owners.pop(canonical_profile, None)

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
            prefs_data["protocol_handler"]["excluded_schemes"]["ms-teams"] = True
            prefs_data["protocol_handler"]["excluded_schemes"]["ms-teams-launcher"] = True
            prefs_data["protocol_handler"]["excluded_schemes"]["ms-word"] = True

            prefs_data.setdefault("profile", {})
            prefs_data["profile"].setdefault(
                "default_content_setting_values",
                {}
            )

            prefs_data["profile"]["default_content_setting_values"][
                "notifications"
            ] = 2
            prefs_data["profile"]["default_content_setting_values"][
                "media_stream_mic"
            ] = 1
            prefs_data["profile"]["default_content_setting_values"][
                "media_stream_camera"
            ] = 1

            with open(prefs_path, "w", encoding="utf-8") as f:
                json.dump(prefs_data, f)

            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--enable-gpu",
                "--ignore-gpu-blocklist",
                "--enable-gpu-rasterization",
                "--enable-zero-copy",
                "--autoplay-policy=no-user-gesture-required",
                "--enable-usermedia-screen-capturing",
                "--auto-select-desktop-capture-source=PowerPoint Slide Show",
            ]

            context = await self.playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(temp_dir),
                channel=settings.EDGE_CHANNEL,
                headless=meeting_bot_config.headless,
                slow_mo=meeting_bot_config.slow_mo,
                args=launch_args,
                viewport={
                    "width": meeting_bot_config.viewport_width,
                    "height": meeting_bot_config.viewport_height,
                },
                permissions=["microphone", "camera"],
            )

            if context.pages:
                page = context.pages[0]
                page._playwright_instance = pw_instance
                page._session_id = session_id
            else:
                page = await context.new_page()
                page._session_id = session_id

            session_obj = BrowserSession(
                browser=None,
                context=context,
                page=page,
            )
            self._sessions[session_id] = session_obj
            self._profile_owners[canonical_profile] = session_id
            self.session = session_obj

            logger.info(f"BrowserManager | SUCCESS launch | Browser ready for session {session_id}")
            return session_obj
        
        except Exception as e:
            logger.exception(f"BrowserManager | FAILED launch: {e}")
            await self._cleanup_playwright(session_id)
            raise

    @property
    def page(self):
        """Return current page."""

        return self.session.page if self.session else None

    @property
    def context(self):
        """Return current browser context."""

        return self.session.context if self.session else None

    async def close(self, session_id: str | None = None) -> None:
        """
        Close browser resources for a specific session_id.
        If session_id is None, closes all sessions or the default session.
        """

        logger.info(f"BrowserManager | START close | Session: {session_id}")

        try:
            if session_id:
                sess = self._sessions.pop(session_id, None)
                if sess:
                    await sess.close()
                if self.session == sess:
                    self.session = next(iter(self._sessions.values()), None)
                # Release profile ownership for this session
                self._profile_owners = {p: s for p, s in self._profile_owners.items() if s != session_id}
                await self._cleanup_playwright(session_id)
            else:
                for sid, sess in list(self._sessions.items()):
                    try:
                        await sess.close()
                    except Exception as s_err:
                        logger.debug(f"BrowserManager | Session {sid} close notice: {s_err}")
                    await self._cleanup_playwright(sid)
                self._sessions.clear()
                self._profile_owners.clear()
                self.session = None

            logger.info(f"BrowserManager | SUCCESS close | Session: {session_id}")

        except Exception as e:
            logger.exception(f"BrowserManager | FAILED close: {e}")

    async def _cleanup_playwright(self, session_id: str | None = None) -> None:
        """
        Stop Playwright instance for a specific session_id.
        """

        try:
            if session_id:
                pw = self._playwright_instances.pop(session_id, None)
                if pw:
                    await pw.stop()
                if self.playwright_instance == pw:
                    self.playwright_instance = next(iter(self._playwright_instances.values()), None)
            else:
                for sid, pw in list(self._playwright_instances.items()):
                    try:
                        await pw.stop()
                    except Exception:
                        pass
                self._playwright_instances.clear()
                self.playwright_instance = None

        except Exception as e:
            logger.exception(f"Failed stopping Playwright: {e}")


# Singleton instance for legacy code
browser_manager = BrowserManager()