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
    async def _run_with_retries(self, action, *, attempts: int = 3, delay: float = 0.5, context: str = "operation"):
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return await action()
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    raise
                logger.warning(f"TeamsController | {context} failed on attempt {attempt}/{attempts}: {exc}")
                if delay > 0:
                    await asyncio.sleep(delay)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"TeamsController | {context} failed without a captured error")

    async def _wait_for_media_state(self, page: Page, *, timeout: int = 15000) -> None:
        await page.wait_for_timeout(250)
        deadline = asyncio.get_running_loop().time() + (timeout / 1000)
        while asyncio.get_running_loop().time() < deadline:
            try:
                mic_btn = page.locator("button[aria-label*='microphone' i], button[data-tid='prejoin-mic-toggle']")
                cam_btn = page.locator("button[aria-label*='camera' i], button[data-tid='prejoin-camera-toggle']")
                if await mic_btn.count() and await cam_btn.count():
                    return
            except Exception:
                pass
            await page.wait_for_timeout(250)

    async def _validate_media_controls(self, page: Page) -> tuple[bool, bool, bool, bool]:
        mic_visible = False
        camera_visible = False
        mic_muted = False
        camera_off = False

        mic_selectors = [
            "button[aria-label*='microphone' i]",
            "button[data-tid='prejoin-mic-toggle']",
        ]
        for selector in mic_selectors:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=1500):
                    mic_visible = True
                    label = await el.get_attribute("aria-label") or ""
                    mic_muted = "mute" in label.lower() or "unmute" in label.lower()
                    break
            except Exception:
                pass

        camera_selectors = [
            "button[aria-label*='camera' i]",
            "button[data-tid='prejoin-camera-toggle']",
            "[role='switch'][aria-label*='camera' i]",
        ]
        for selector in camera_selectors:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=1500):
                    camera_visible = True
                    label = await el.get_attribute("aria-label") or ""
                    aria_checked = await el.get_attribute("aria-checked")
                    if aria_checked is not None:
                        camera_off = aria_checked.lower() == "false"
                    else:
                        camera_off = "off" in label.lower() or "disabled" in label.lower()
                    break
            except Exception:
                pass

        return mic_visible, mic_muted, camera_visible, camera_off

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

        deadline = asyncio.get_running_loop().time() + 10

        while asyncio.get_running_loop().time() < deadline:
            for p in context.pages:
                if (
                    "teams.live.com" in p.url
                    or "teams.microsoft.com" in p.url
                    or "light-meetings" in p.url
                ):
                    p._session_id = sess_id
                    page = p
                    logger.info(f"TeamsController | [JOIN] Bound to Teams page: {page.url}")
                    break

            if (
                "teams.live.com" in page.url
                or "teams.microsoft.com" in page.url
            ):
                break

            await asyncio.sleep(0.25)

        if not (
            "teams.live.com" in page.url
            or "teams.microsoft.com" in page.url
        ):
            raise RuntimeError(f"TeamsController | [JOIN] Teams page did not become ready: {page.url}")

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

        logger.info("TeamsController | [JOIN] Waiting for Teams prejoin page...")

        timeout = asyncio.get_running_loop().time() + 12

        while asyncio.get_running_loop().time() < timeout:
            logger.info(f"TeamsController | [JOIN] Waiting for prejoin UI: {page.url}")
            try:
                logger.info(f"TeamsController | [JOIN] Page title -> {await page.title()}")
            except Exception:
                pass

            for p in page.context.pages:
                if p.is_closed():
                    continue
                if (
                    "teams.live.com" in p.url
                    or "teams.microsoft.com" in p.url
                    or "launcher.html" in p.url
                ):
                    if p != page:
                        logger.info(f"TeamsController | [JOIN] Switching to active page: {p.url}")
                        page = p
                        break

            if page.is_closed():
                raise RuntimeError("TeamsController | [JOIN] Teams page was closed.")

            current_url = page.url.rstrip("/")
            if current_url == "https://teams.live.com/v2":
                break

            await asyncio.sleep(0.5)

        current_url = page.url.rstrip("/")

        if current_url == "https://teams.live.com/v2":

            try:
                title = await page.title()

                logger.info(
                    f"TeamsController | /v2/ detected. Current title: {title}"
                )

                # If we're already in the meeting flow, don't interfere.
                if "Meeting join" in title:
                    logger.info(
                        "TeamsController | Meeting join page detected. Waiting..."
                    )

                elif title.strip() == "Microsoft Teams":

                    logger.warning(
                        "TeamsController | Teams home detected. Waiting for automatic redirect..."
                    )

                    await asyncio.sleep(5)

            except Exception:
                pass

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
                await page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=3000,
                )
            except Exception:
                pass

            PREJOIN_SELECTORS = [
                "button[data-tid='prejoin-join-button']",
                "input[data-tid='prejoin-display-name']",
                "button:has-text('Join now')",
                "button[aria-label*='Join']",
            ]

            found = False
            for selector in PREJOIN_SELECTORS:
                try:
                    await page.wait_for_selector(
                        selector,
                        timeout=1500,
                    )
                    logger.info(f"TeamsController | [JOIN] Matched selector -> {selector}")
                    found = True
                    break
                except Exception:
                    pass

            if found:
                return page

            await asyncio.sleep(0.5)

        logger.error(
            f"TeamsController | [JOIN] Prejoin timeout. Final URL: {page.url}"
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
        logger.info(f"TeamsController | [JOIN] Configuring pre-join devices (mute_mic={mute_mic}, turn_off_cam={turn_off_cam})")
        
        await self._wait_for_media_state(page, timeout=6000)
        
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
            "button[data-tid='prejoin-camera-toggle']",
            "button[aria-label*='camera' i]:not([aria-haspopup])",
            "button[aria-label*='video' i]:not([aria-haspopup])",
            "[role='switch'][aria-label*='camera' i]",
            "[role='switch'][aria-label*='video' i]",
            "button[aria-label*='camera' i]",
            "button[aria-label*='video' i]",
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

        mic_visible, mic_muted, camera_visible, camera_off = await self._validate_media_controls(page)
        if not mic_visible:
            logger.warning("TeamsController | Microphone control did not become visible in pre-join UI")
        if not camera_visible:
            logger.warning("TeamsController | Camera control did not become visible in pre-join UI")

        # Capture 03_devices_configured
        sess_id = getattr(page, "_session_id", "verification_session")
        await screen_capture.capture_step(page, sess_id, "devices_configured")

        msg = (
            f"Devices configured (Mic found: {mic_found}, disabled: {mic_disabled}; "
            f"Cam found: {cam_found}, disabled: {cam_disabled}; "
            f"Mic visible: {mic_visible}, muted: {mic_muted}; Camera visible: {camera_visible}, off: {camera_off})"
        )
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
        logger.info(f"TeamsController | [JOIN] Entering guest name: {display_name}")
        
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
        
        async def click_join_button():
            for sel in join_selectors:
                try:
                    el = page.locator(sel)
                    await el.wait_for(state="visible", timeout=3000)
                    await el.click()
                    logger.info(f"TeamsController | [JOIN] Clicked join button: '{sel}'")
                    return
                except Exception:
                    pass
            raise RuntimeError("TeamsController | [JOIN] Join button not found in prejoin UI")

        await self._run_with_retries(click_join_button, attempts=2, delay=0.25, context="join button click")

    async def leave_meeting(self, page: Page) -> None:
        """
        Hangup the active call.
        """
        if page.is_closed():
            logger.info("TeamsController | Page is already closed. Skipping hangup click.")
            return

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

    async def share_powerpoint(self, page: Page) -> bool:
        """
        Alias/wrapper for PowerPoint Slide Show window sharing in Teams.
        """
        return await self.share_presentation_window(page, "PowerPoint")

    async def open_share_panel(self, page: Page) -> None:
        """Open the Teams share panel and stop before native picker selection."""
        if page.is_closed():
            raise RuntimeError("Teams page closed during share panel open")

        share_selectors = [
            "button[data-tid='toolbar-share-button']",
            "button[aria-label*='Share' i]",
            "button:has-text('Share')",
        ]

        for selector in share_selectors:
            try:
                button = page.locator(selector)
                if await button.is_visible(timeout=3000):
                    await button.click()
                    logger.info("TeamsController | Opened share panel")
                    return
            except Exception:
                pass

        raise RuntimeError("Teams share button not found")

    async def confirm_share(self, page: Page) -> bool:
        """Wait for Teams to confirm that sharing has started."""
        validation_selectors = [
            "button[data-tid='stop-presenting-button']",
            "button[aria-label*='Stop sharing' i]",
            "button:has-text('Stop sharing')",
            "text=You're presenting",
        ]

        for _ in range(10):
            if page.is_closed():
                raise RuntimeError("Teams page closed during share validation")
            for selector in validation_selectors:
                try:
                    if await page.locator(selector).first.is_visible(timeout=200):
                        logger.success("TeamsController | Presentation sharing started.")
                        return True
                except Exception:
                    pass
            await page.wait_for_timeout(500)

        raise RuntimeError("TeamsController | Presentation sharing verification failed")

    async def _wait_for_ui(self, page: Page, selectors: list[str], *, timeout: float = 5.0) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if page.is_closed():
                raise RuntimeError("Teams page closed during share flow")
            for selector in selectors:
                try:
                    if await page.locator(selector).first.is_visible(timeout=200):
                        return True
                except Exception:
                    pass
            await page.wait_for_timeout(250)
        return False

    async def share_presentation_window(self, page: Page, window_name: str = "PowerPoint") -> bool:
        """
        Open the Teams share panel, hand off to native picker selection, and confirm the share.
        """
        if page.is_closed():
            return False

        # Click "Screen, window" share option
        share_option_clicked = False
        for selector in [
            "[aria-label*='Screen, window' i]",
            "[aria-label*='Screen sharing' i]",
            "[aria-label*='Share screen' i]",
            "button:has-text('Screen, window')",
            "span:has-text('Screen, window')",
            "div:has-text('Screen, window')",
        ]:
            try:
                option = page.locator(selector)
                if await option.is_visible(timeout=2000):
                    await option.click()
                    logger.info(f"TeamsController | Clicked share option selector: {selector}")
                    share_option_clicked = True
                    break
            except Exception:
                pass
        if not share_option_clicked:
            raise RuntimeError("TeamsController | Screen, window share option not found")

        # Native picker auto-selects due to launch flags; verify sharing started
        from app.modules.presentation.share_verification_controller import ShareVerificationController
        verification = ShareVerificationController()
        return await verification.wait_for_share_confirmation(page)



    async def stop_sharing(self, page: Page) -> None:
        if page.is_closed():
            return

        selectors = [
            "button[data-tid='stop-presenting-button']",
            "button[aria-label*='Stop sharing' i]",
            "button:has-text('Stop sharing')",
        ]
        for selector in selectors:
            try:
                button = page.locator(selector)
                if await button.is_visible(timeout=2000):
                    await button.click()
                    logger.info("TeamsController | Stopped sharing.")
                    return
            except Exception:
                pass

teams_controller = TeamsController()
