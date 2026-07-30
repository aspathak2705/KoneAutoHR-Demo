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
        sharing_selectors = [
            "[data-tid='powerpoint-live-view']",
            "[data-tid='ppt-presentation']",
            "div.ppt-stage",
            "iframe[src*='powerpoint' i]",
            "[data-tid='stage-sharing-overlay']",
            "[data-tid='share-stage']",
            "video[aria-label*='Screen' i]",
            "video[aria-label*='Shared' i]",
            "video[aria-label*='Share' i]",
            "video[aria-label*='Present' i]",
            "video[aria-label*='Presentation' i]",
            "div[aria-label*='Shared screen' i]",
            "div[aria-label*='screen' i]",
            "div[aria-label*='shared' i]",
            "div[aria-label*='present' i]",
            "div[aria-label*='presentation' i]",
            "div[class*='screen-share' i]",
            "div[class*='share-stage' i]",
            "[data-tid*='sharing' i]",
            "[data-tid*='stage' i]"
        ]
        
        for sel in sharing_selectors:
            try:
                locator = page.locator(sel).first
                if await locator.is_visible(timeout=200):
                    # Capture locator screenshot directly
                    screenshot_bytes = await locator.screenshot(type="png", timeout=3000)
                    logger.info(f"PresentationViewportProvider | Captured screenshot for selector: {sel}")
                    return screenshot_bytes, sel
            except Exception:
                pass

        # Robust Fallback: Scan for the largest visible video element (likely screen sharing)
        try:
            videos = await page.locator("video").all()
            largest_video = None
            largest_area = 0
            
            for v in videos:
                try:
                    if await v.is_visible(timeout=100):
                        box = await v.bounding_box()
                        if box:
                            area = box["width"] * box["height"]
                            if area > largest_area and box["width"] > 400 and box["height"] > 300:
                                largest_area = area
                                largest_video = v
                except Exception:
                    pass
            
            if largest_video:
                screenshot_bytes = await largest_video.screenshot(type="png", timeout=3000)
                logger.info(f"PresentationViewportProvider | Found sharing video by surface area size fallback ({largest_area}px).")
                return screenshot_bytes, "video"
        except Exception as e:
            logger.error(f"PresentationViewportProvider | Fallback video scan failed: {e}")
                
        return None, None

presentation_viewport_provider = PresentationViewportProvider()
