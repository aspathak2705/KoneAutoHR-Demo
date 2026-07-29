import asyncio
from dataclasses import dataclass
from playwright.async_api import Page
from loguru import logger
from app.modules.meeting_bot.media.screen_capture import screen_capture

@dataclass
class DeviceConfigurationResult:
    microphone_found: bool
    microphone_disabled: bool
    camera_found: bool
    camera_disabled: bool
    message: str

class TeamsController:
    async def open_meeting(self, page: Page, url: str) -> Page:
        """
        Navigate to Teams meeting and bind to the final Teams page.
        """

        sess_id = getattr(page, "_session_id", "verification_session")
        page.context._meeting_url = url
        logger.info(f"TeamsController | Opening meeting URL: {url}")

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        browser_selectors = [
            "button[data-tid='join-on-web']",
            "button:has-text('Continue on this browser')",
            "button:has-text('Join on the web')",
            "#openTeamsClientInBrowser",
            "text=Continue on this browser",
        ]

        context = page.context
        button_clicked = False

        for selector in browser_selectors:

            try:
                button = page.locator(selector)
                await button.wait_for(state="visible", timeout=10000)

                try:
                    from app.modules.meeting_bot.desktop.desktop_controller import (
                        desktop_controller,
                    )

                    await page.bring_to_front()
                    desktop_controller.focus_teams()
                    desktop_controller.dismiss_popup()
                    await asyncio.sleep(0.5)
                    desktop_controller.dismiss_popup()
                except Exception:
                    pass

                logger.info(
                    f"TeamsController | Clicking browser option: {selector}"
                )

                await button.click(force=True)

                button_clicked = True
                break

            except Exception as e:
                logger.debug(
                    f"Selector '{selector}' unavailable: {e}"
                )

        if not button_clicked:
            logger.warning(
                "TeamsController | Continue on browser button not found."
            )

        logger.info("TeamsController | Waiting for Teams navigation...")

        deadline = asyncio.get_running_loop().time() + 30

        while asyncio.get_running_loop().time() < deadline:

            for p in context.pages:

                logger.info(f"Observed page: {p.url}")

                if (
                    "teams.live.com" in p.url
                    or "teams.microsoft.com" in p.url
                    or "light-meetings" in p.url
                ):
                    p._session_id = sess_id
                    page = p
                    break

            if (
                "teams.live.com" in page.url
                or "teams.microsoft.com" in page.url
            ):
                break

            await asyncio.sleep(0.5)

        logger.info(f"Bound page: {page.url}")

        # ---------- Navigation Diagnostics ----------

        page.on(
            "framenavigated",
            lambda frame: logger.info(
                f"FRAME NAVIGATED -> {frame.url}"
            ),
        )

        page.on(
            "close",
            lambda: logger.warning("PAGE CLOSED"),
        )

        page.on(
            "crash",
            lambda: logger.error("PAGE CRASHED"),
        )

        # --------------------------------------------

        await screen_capture.capture_step(
            page,
            sess_id,
            "meeting_loaded",
        )

        return page
    async def wait_for_prejoin(self, page: Page) -> Page:
        """
        Wait until Teams prejoin controls appear.
        """

        if "launcher.html" in page.url:

            logger.info(
                "TeamsController | Launcher page detected. "
                "Searching context pages..."
            )

            for p in page.context.pages:

                logger.info(f"Context page: {p.url}")

                if (
                    "teams.live.com" in p.url
                    or "teams.microsoft.com" in p.url
                    or "light-meetings" in p.url
                ):
                    page = p
                    logger.info(f"Re-bound page -> {page.url}")
                    break

        logger.info("========== PREJOIN DEBUG ==========")
        logger.info(f"Current URL : {page.url}")
        logger.info(f"Closed      : {page.is_closed()}")
        logger.info(f"Pages       : {len(page.context.pages)}")

        for i, p in enumerate(page.context.pages):
            logger.info(f"Context Page {i}: {p.url}")

        logger.info("===================================")

        logger.info("Waiting for Teams prejoin page...")

        timeout = asyncio.get_running_loop().time() + 30

        while asyncio.get_running_loop().time() < timeout:

            logger.info(f"Polling URL -> {page.url}")

            if page.is_closed():
                raise RuntimeError("Teams page was closed.")

            if "chrome-error" in page.url:
                logger.warning(
                    f"TeamsController | Detected error page '{page.url}'. Attempting page reload to bypass silent auth deadlock..."
                )
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(1)
                    if "chrome-error" in page.url:
                        # Fallback navigation back to the meeting URL directly
                        meet_url = getattr(page.context, "_meeting_url", None)
                        if meet_url:
                            logger.info(f"TeamsController | Reload failed. Re-navigating to meeting URL: {meet_url}")
                            await page.goto(meet_url, wait_until="domcontentloaded", timeout=15000)
                except Exception as reload_err:
                    logger.error(f"TeamsController | Page reload/goto failed: {reload_err}")

            try:

                await page.wait_for_selector(
                    "input[data-tid='prejoin-display-name'], "
                    "button[data-tid='prejoin-join-button']",
                    timeout=1000,
                )

                logger.info(
                    "TeamsController | Prejoin controls detected."
                )

                return page

            except Exception:
                pass

            await asyncio.sleep(0.5)

        logger.error(
            f"Prejoin timeout. Final URL: {page.url}"
        )

        sess_id = getattr(page, "_session_id", "verification_session")
        screenshot = await screen_capture.capture_step(
            page,
            sess_id,
            "prejoin_wait_failed",
        )

        logger.info(f"Diagnostic screenshot: {screenshot}")

        raise RuntimeError(
            f"Timed out waiting for Teams prejoin UI. "
            f"Current URL: {page.url}"
        )

    async def configure_devices(self, page: Page, mute_mic: bool = True, turn_off_cam: bool = True) -> DeviceConfigurationResult:
        """
        Interacts with toggle pre-join buttons for camera and microphone permissions.
        Returns typed DeviceConfigurationResult dataclass.
        """
        logger.info(f"TeamsController | Configuring pre-join devices (mute_mic={mute_mic}, turn_off_cam={turn_off_cam})")
        
        try:
            await page.locator("button[aria-label*='microphone' i]").wait_for(state="visible", timeout=20000)
        except Exception as e:
            logger.warning(f"TeamsController | Timeout waiting for mic toggle button to be visible: {e}")

        mic_found = False
        cam_found = False
        mic_disabled = False
        cam_disabled = False

        # Mute Microphone
        mic_selectors = [
            "button[aria-label*='microphone' i]",
            "button[aria-label*='mute' i]",
            "button[data-tid='prejoin-mic-toggle']"
        ]
        for sel in mic_selectors:
            try:
                el = page.locator(sel)
                if await el.is_visible(timeout=2000):
                    mic_found = True
                    label = await el.get_attribute("aria-label") or ""
                    if "mute" not in label.lower() or "unmute" in label.lower():
                        if mute_mic:
                            await el.click()
                            mic_disabled = True
                            logger.info("TeamsController | Microphone toggled (muted)")
                    else:
                        mic_disabled = True
                    break
            except Exception as e:
                logger.debug(f"TeamsController | Mic selector '{sel}' visibility check failed: {e}")

        # Turn Off Camera
        cam_selectors = [
            "button[aria-label*='camera' i]",
            "button[aria-label*='video' i]",
            "button[data-tid='prejoin-camera-toggle']",
            "//button[contains(@class, 'toggle') or contains(@role, 'checkbox')][contains(.., 'Background') or contains(.., 'Camera')]"
        ]
        for sel in cam_selectors:
            try:
                el = page.locator(sel)
                if await el.is_visible(timeout=2000):
                    cam_found = True
                    label = await el.get_attribute("aria-label") or ""
                    # Check checkbox checked status if it exists as checkbox/toggle role
                    checked_attr = await el.get_attribute("aria-checked")
                    role = await el.get_attribute("role")
                    
                    if role == "checkbox" or role == "switch":
                        is_on = checked_attr == "true"
                        if is_on and turn_off_cam:
                            await el.click()
                            cam_disabled = True
                            logger.info("TeamsController | Camera checkbox toggle clicked (turned off)")
                        elif not is_on:
                            cam_disabled = True
                    elif "off" not in label.lower():
                        if turn_off_cam:
                            await el.click()
                            cam_disabled = True
                            logger.info("TeamsController | Camera toggled (turned off)")
                    else:
                        cam_disabled = True
                    break
            except Exception as e:
                logger.debug(f"TeamsController | Cam selector '{sel}' visibility check failed: {e}")

        # Capture 03_devices_configured
        sess_id = getattr(page, "_session_id", "verification_session")
        await screen_capture.capture_step(page, sess_id, "devices_configured")

        msg = f"Devices configured (Mic found: {mic_found}, disabled: {mic_disabled}; Cam found: {cam_found}, disabled: {cam_disabled})"
        logger.info(f"TeamsController | {msg}")

        return DeviceConfigurationResult(
            microphone_found=mic_found,
            camera_found=cam_found,
            microphone_disabled=mic_disabled,
            camera_disabled=cam_disabled,
            message=msg
        )

    async def enter_name_and_join(self, page: Page, display_name: str) -> None:
        """
        Enters name input box and clicks 'Join now'.
        """
        logger.info(f"TeamsController | Entering guest name: {display_name}")
        
        name_selectors = [
            "input[data-tid='prejoin-display-name']",
            "input[aria-label*='name' i]",
            "input[placeholder*='name' i]"
        ]
        
        name_input_found = False
        for sel in name_selectors:
            try:
                el = page.locator(sel)
                await el.wait_for(state="visible", timeout=3000)
                await el.fill(display_name)
                logger.info(f"TeamsController | Entered name using: '{sel}'")
                name_input_found = True
                break
            except Exception:
                pass

        if not name_input_found:
            # Check if profile configuration is connected
            from app.db.database import SessionLocal
            from app.services.agent_configuration_service import agent_configuration_service
            is_connected = False
            with SessionLocal() as db:
                is_connected = agent_configuration_service.get_connection_state(db)
            if is_connected:
                logger.info("TeamsController | Name input not found in authenticated context. Bypassing guest name entry.")
            else:
                logger.warning("TeamsController | Name input not found, but agent config is not connected.")

        # Capture 04_join_requested
        sess_id = getattr(page, "_session_id", "verification_session")
        await screen_capture.capture_step(page, sess_id, "join_requested")

        # Join Now
        join_selectors = [
            "button[data-tid='prejoin-join-button']",
            "button:has-text('Join now')",
            "button[aria-label*='Join' i]"
        ]
        
        for sel in join_selectors:
            try:
                el = page.locator(sel)
                await el.wait_for(state="visible", timeout=10000)
                await el.click()
                logger.info(f"TeamsController | Clicked join button: '{sel}'")
                break
            except Exception:
                pass

    async def leave_meeting(self, page: Page) -> None:
        """
        Hangup the active call.
        """
        logger.info("TeamsController | Leaving meeting...")
        leave_selectors = [
            "button[data-tid='hangup-button']",
            "button[aria-label*='Leave' i]",
            "#hangup-button"
        ]
        for sel in leave_selectors:
            try:
                el = page.locator(sel)
                if await el.is_visible(timeout=2000):
                    await el.click()
                    logger.info("TeamsController | Clicked hangup button.")
                    await asyncio.sleep(2)
                    break
            except Exception:
                pass

teams_controller = TeamsController()
