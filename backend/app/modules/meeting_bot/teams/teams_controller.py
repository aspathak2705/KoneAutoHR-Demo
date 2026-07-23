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
    async def open_meeting(self, page: Page, url: str) -> None:
        """
        Navigates to Teams URL and handles the 'Continue on this browser' modal option.
        """
        logger.info(f"TeamsController | Opening meeting URL: {url}")
        await page.goto(url)
        await asyncio.sleep(2.5)
        
        # Focus window and dismiss native protocol handler popup dialog (Open Microsoft Teams?)
        try:
            from app.modules.meeting_bot.desktop.desktop_controller import desktop_controller
            desktop_controller.focus_teams()
            desktop_controller.dismiss_popup()
            await asyncio.sleep(0.5)
            desktop_controller.dismiss_popup()
        except Exception:
            pass
        
        await asyncio.sleep(1) # Extra buffer
        
        # Look for "Join on this browser" or "Continue on this browser"
        browser_selectors = [
            "button[data-tid='join-on-web']",
            "button:has-text('Continue on this browser')",
            "button:has-text('Join on the web')",
            "#openTeamsClientInBrowser",
            "text=Continue on this browser"
        ]
        
        button_found = False
        for sel in browser_selectors:
            try:
                el = page.locator(sel)
                await el.wait_for(state="visible", timeout=10000)
                logger.info(f"TeamsController | Clicking browser option selector: '{sel}'")
                await el.click()
                button_found = True
                break
            except Exception:
                pass
                
        if not button_found:
            logger.warning("TeamsController | 'Continue on this browser' button not found or already bypassed.")

        # Capture 02_meeting_loaded
        await screen_capture.capture_step(page, "verification_session", "meeting_loaded")

    async def configure_devices(self, page: Page, mute_mic: bool = True, turn_off_cam: bool = True) -> DeviceConfigurationResult:
        """
        Interacts with toggle pre-join buttons for camera and microphone permissions.
        Returns typed DeviceConfigurationResult dataclass.
        """
        logger.info(f"TeamsController | Configuring pre-join devices (mute_mic={mute_mic}, turn_off_cam={turn_off_cam})")
        
        try:
            await page.locator("button[aria-label*='microphone' i]").wait_for(state="visible", timeout=20000)
        except Exception:
            logger.warning("TeamsController | Timeout waiting for mic toggle button to be visible. Trying pre-join inputs...")

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
            except Exception:
                pass

        # Turn Off Camera
        cam_selectors = [
            "button[aria-label*='camera' i]",
            "button[aria-label*='video' i]",
            "button[data-tid='prejoin-camera-toggle']"
        ]
        for sel in cam_selectors:
            try:
                el = page.locator(sel)
                if await el.is_visible(timeout=2000):
                    cam_found = True
                    label = await el.get_attribute("aria-label") or ""
                    if "off" not in label.lower():
                        if turn_off_cam:
                            await el.click()
                            cam_disabled = True
                            logger.info("TeamsController | Camera toggled (turned off)")
                    else:
                        cam_disabled = True
                    break
            except Exception:
                pass

        # Capture 03_devices_configured
        await screen_capture.capture_step(page, "verification_session", "devices_configured")

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
        
        for sel in name_selectors:
            try:
                el = page.locator(sel)
                await el.wait_for(state="visible", timeout=15000)
                await el.fill(display_name)
                logger.info(f"TeamsController | Entered name using: '{sel}'")
                break
            except Exception:
                pass

        # Capture 04_join_requested
        await screen_capture.capture_step(page, "verification_session", "join_requested")

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
