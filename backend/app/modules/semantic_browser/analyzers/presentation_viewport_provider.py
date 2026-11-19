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
                            if area > largest_area and box["width"] > 200 and box["height"] > 150:
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
