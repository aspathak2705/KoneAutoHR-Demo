import asyncio
from playwright.async_api import Page
from loguru import logger

class TeamsController:
    async def open_meeting(self, page: Page, url: str) -> None:
        """
        Navigates to Teams URL and handles the 'Continue on this browser' modal option.
        """
        logger.info(f"TeamsController | Opening meeting URL: {url}")
        await page.goto(url)
        await asyncio.sleep(5) # Wait for page initial rendering
        
        # Look for "Join on this browser" or "Continue on this browser"
        browser_selectors = [
            "button[data-tid='join-on-web']",
            "button:has-text('Continue on this browser')",
            "button:has-text('Join on the web')",
            "#openTeamsClientInBrowser",
            "text=Continue on this browser"
        ]
        
        for sel in browser_selectors:
            try:
                el = page.locator(sel)
                if await el.is_visible(timeout=2000):
                    logger.info(f"TeamsController | Clicking browser option selector: '{sel}'")
                    await el.click()
                    await asyncio.sleep(4)
                    break
            except Exception:
                pass

    async def configure_devices(self, page: Page, mute_mic: bool = True, turn_off_cam: bool = True) -> None:
        """
        Interacts with toggle pre-join buttons for camera and microphone permissions.
        """
        logger.info(f"TeamsController | Configuring pre-join devices (mute_mic={mute_mic}, turn_off_cam={turn_off_cam})")
        
        # Mute Mic
        if mute_mic:
            mic_selectors = [
                "button[aria-label*='microphone' i]",
                "button[aria-label*='mute' i]",
                "button[data-tid='prejoin-mic-toggle']"
            ]
            for sel in mic_selectors:
                try:
                    el = page.locator(sel)
                    if await el.is_visible(timeout=2000):
                        # Verify if already muted
                        label = await el.get_attribute("aria-label") or ""
                        if "mute" not in label.lower() or "unmute" in label.lower():
                            await el.click()
                            logger.info("TeamsController | Microphone toggled (muted)")
                        break
                except Exception:
                    pass

        # Turn Off Camera
        if turn_off_cam:
            cam_selectors = [
                "button[aria-label*='camera' i]",
                "button[aria-label*='video' i]",
                "button[data-tid='prejoin-camera-toggle']"
            ]
            for sel in cam_selectors:
                try:
                    el = page.locator(sel)
                    if await el.is_visible(timeout=2000):
                        label = await el.get_attribute("aria-label") or ""
                        if "off" not in label.lower():
                            await el.click()
                            logger.info("TeamsController | Camera toggled (turned off)")
                        break
                except Exception:
                    pass

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
                if await el.is_visible(timeout=2000):
                    await el.fill(display_name)
                    logger.info(f"TeamsController | Entered name using: '{sel}'")
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass

        # Join Now
        join_selectors = [
            "button[data-tid='prejoin-join-button']",
            "button:has-text('Join now')",
            "button[aria-label*='Join' i]"
        ]
        
        for sel in join_selectors:
            try:
                el = page.locator(sel)
                if await el.is_visible(timeout=2000):
                    await el.click()
                    logger.info(f"TeamsController | Clicked join button: '{sel}'")
                    await asyncio.sleep(5)
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
