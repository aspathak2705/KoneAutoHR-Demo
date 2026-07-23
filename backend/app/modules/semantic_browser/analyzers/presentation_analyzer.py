from playwright.async_api import Page
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from loguru import logger

class PresentationAnalyzer:
    async def analyze(self, page: Page) -> dict:
        """
        Determines presentation status (Screen sharing, PowerPoint share, Video playback, Blank/Waiting, Loading, Ended).
        """
        mode = PresentationMode.NONE
        details = {}

        # 1. Check PowerPoint Live view
        pp_selectors = [
            "[data-tid='powerpoint-live-view']",
            "[data-tid='ppt-presentation']",
            "div.ppt-stage",
            "iframe[src*='powerpoint' i]"
        ]
        pp_found = False
        for sel in pp_selectors:
            try:
                if await page.locator(sel).is_visible(timeout=500):
                    pp_found = True
                    details["selector_matched"] = sel
                    break
            except Exception:
                pass

        if pp_found:
            mode = PresentationMode.POWERPOINT_SHARED
            logger.debug("PresentationAnalyzer | PowerPoint Live view detected.")
        else:
            # 2. Check Screen Sharing Stage
            sharing_selectors = [
                "[data-tid='stage-sharing-overlay']",
                "[data-tid='share-stage']",
                "video[aria-label*='Screen' i]",
                "div[aria-label*='Shared screen' i]"
            ]
            sharing_found = False
            for sel in sharing_selectors:
                try:
                    if await page.locator(sel).is_visible(timeout=500):
                        sharing_found = True
                        details["selector_matched"] = sel
                        break
                except Exception:
                    pass
                    
            if sharing_found:
                mode = PresentationMode.SCREEN_SHARING
                logger.debug("PresentationAnalyzer | Screen sharing stage detected.")
            else:
                # 3. Check Active Video Streams (Multiple video feeds = Video playback/grid active)
                video_count = 0
                try:
                    video_count = await page.locator("video").count()
                except Exception:
                    pass
                    
                if video_count > 0:
                    mode = PresentationMode.VIDEO_PLAYBACK
                    details["video_elements_count"] = video_count
                    logger.debug(f"PresentationAnalyzer | {video_count} active video streams detected.")
                else:
                    # 4. Check for Loading / Ended Presentation Indicators
                    ended_selectors = [
                        "text=Presentation ended",
                        "text=stopped sharing",
                        "text=Sharing has ended"
                    ]
                    ended_found = False
                    for sel in ended_selectors:
                        try:
                            if await page.locator(sel).is_visible(timeout=500):
                                ended_found = True
                                break
                        except Exception:
                            pass

                    loading_selectors = [
                        "text=Loading presentation",
                        "text=Starting share",
                        "[data-tid='loader-spinner']"
                    ]
                    loading_found = False
                    for sel in loading_selectors:
                        try:
                            if await page.locator(sel).is_visible(timeout=500):
                                loading_found = True
                                break
                        except Exception:
                            pass

                    # 5. Check for Blank/Waiting Screen
                    waiting_selectors = [
                        "text=Waiting for others to join",
                        "text=Waiting to start",
                        "[data-tid='meeting-waiting-screen']"
                    ]
                    waiting_found = False
                    for sel in waiting_selectors:
                        try:
                            if await page.locator(sel).is_visible(timeout=500):
                                waiting_found = True
                                break
                        except Exception:
                            pass
                            
                    if ended_found:
                        mode = PresentationMode.ENDED
                    elif loading_found:
                        mode = PresentationMode.LOADING
                    elif waiting_found:
                        mode = PresentationMode.WAITING_SCREEN
                    else:
                        mode = PresentationMode.NONE

        return {
            "mode": mode,
            "details": details
        }

presentation_analyzer = PresentationAnalyzer()
