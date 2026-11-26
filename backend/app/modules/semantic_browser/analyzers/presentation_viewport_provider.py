from playwright.async_api import Page
from loguru import logger
from typing import Optional, Tuple

class PresentationViewportProvider:
    async def get_viewport_screenshot(self, page: Page) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Locates the presentation region using Teams stage elements and captures a targeted element screenshot.
        Works even when Chromium is covered by other windows.
        Returns:
            Tuple[Optional[bytes], Optional[str]]: (screenshot_bytes, matched_selector)
        """
        if page.is_closed():
            return None, None
            
        sharing_selectors = [
            "[data-tid='powerpoint-live-view']",
            "[data-tid='ppt-presentation']",
            "div.ppt-stage",
            "iframe[src*='powerpoint' i]",
            "[data-tid='stage-sharing-overlay']",
            "[data-tid='screen-player-container']",
            "div[data-cid='stream-player']",
            "[data-tid='presenting-screen']",
            "video[aria-label*='Screen' i]",
            "video[aria-label*='Shared screen' i]",
            "video[aria-label*='Presentation' i]",
            "div[data-tid='share-stage'] video"
        ]
        
        for sel in sharing_selectors:
            try:
                locator = page.locator(sel).first
                if await locator.is_visible(timeout=200):
                    # Verify element has presentation stage dimensions (>320x240)
                    box = await locator.bounding_box()
                    if not box or box["width"] < 320 or box["height"] < 240:
                        continue
                    # Capture locator screenshot directly
                    screenshot_bytes = await locator.screenshot(type="png", timeout=3000)
                    logger.info(f"PresentationViewportProvider | Captured screenshot for selector: {sel} ({int(box['width'])}x{int(box['height'])})")
                    return screenshot_bytes, sel
            except Exception:
                pass

        return None, None

presentation_viewport_provider = PresentationViewportProvider()
