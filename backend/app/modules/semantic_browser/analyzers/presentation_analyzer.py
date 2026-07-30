from playwright.async_api import Page
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.semantic_browser.models.semantic_state import DOMSummary
from loguru import logger
import hashlib
import json
import io
from app.services.storage_service import storage_service

class PresentationAnalyzer:
    async def analyze(self, page: Page, dom: DOMSummary = None) -> dict:
        """
        Determines presentation status and matches slides using PresentationViewportProvider.
        Works in background covered states.
        """
        from app.modules.semantic_browser.analyzers.presentation_viewport_provider import presentation_viewport_provider

        mode = PresentationMode.NONE
        details = {}
        signature = None
        current_slide = 0
        confidence = 0.0

        # Query Playwright locator viewport screenshot
        screenshot_bytes, matched_sel = await presentation_viewport_provider.get_viewport_screenshot(page)

        if screenshot_bytes and matched_sel:
            details["selector_matched"] = matched_sel
            # Identify exact share mode
            if matched_sel in ["[data-tid='powerpoint-live-view']", "[data-tid='ppt-presentation']", "div.ppt-stage", "iframe[src*='powerpoint' i]"]:
                mode = PresentationMode.POWERPOINT_SHARED
            else:
                mode = PresentationMode.SCREEN_SHARING

            try:
                # Read session fingerprints from preprocessed assets
                session_id = getattr(page, "_session_id", None)
                if session_id:
                    assets_dir = storage_service.get_session_dir(session_id) / "presentation_assets"
                    fingerprints_file = assets_dir / "fingerprints.json"
                    
                    if fingerprints_file.exists():
                        with open(fingerprints_file, "r", encoding="utf-8") as f:
                            fingerprints = json.load(f)
                        
                        # Calculate perceptual hash of cropped live screenshot
                        from PIL import Image
                        img = Image.open(io.BytesIO(screenshot_bytes)).convert('L').resize((8, 8), Image.Resampling.LANCZOS)
                        pixels = list(img.getdata())
                        avg = sum(pixels) / 64.0
                        live_hash = "".join("1" if p >= avg else "0" for p in pixels)
                        
                        # Compare Hamming distances
                        best_match = None
                        best_dist = 65
                        for slide_name, fp in fingerprints.items():
                            fp_hash = fp["phash"]
                            dist = sum(c1 != c2 for c1, c2 in zip(live_hash, fp_hash))
                            if dist < best_dist:
                                best_dist = dist
                                best_match = slide_name
                        
                        if best_match:
                            import re
                            num_match = re.search(r'\d+', best_match)
                            if num_match:
                                current_slide = int(num_match.group())
                                confidence = (64.0 - best_dist) / 64.0
                                # Robust slide index signature mapping
                                signature = f"slide_{current_slide}"
                                details["matched_slide_file"] = best_match
                                details["hamming_distance"] = best_dist
            except Exception as e:
                logger.error(f"PresentationAnalyzer | Failed slide matching: {e}")
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
                logger.debug(f"PresentationAnalyzer | {video_count} active video feeds detected.")
            else:
                # 4. Check for Loading / Ended / Waiting Screen
                ended_selectors = ["text=Presentation ended", "text=stopped sharing", "text=Sharing has ended"]
                ended_found = False
                for sel in ended_selectors:
                    try:
                        if await page.locator(sel).is_visible(timeout=200):
                            ended_found = True
                            break
                    except Exception:
                        pass

                loading_selectors = ["text=Loading presentation", "text=Starting share", "[data-tid='loader-spinner']"]
                loading_found = False
                for sel in loading_selectors:
                    try:
                        if await page.locator(sel).is_visible(timeout=200):
                            loading_found = True
                            break
                    except Exception:
                        pass

                waiting_selectors = ["text=Waiting for others to join", "text=Waiting to start", "[data-tid='meeting-waiting-screen']"]
                waiting_found = False
                for sel in waiting_selectors:
                    try:
                        if await page.locator(sel).is_visible(timeout=200):
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
            "signature": signature,
            "current_slide": current_slide,
            "confidence": confidence,
            "details": details
        }

presentation_analyzer = PresentationAnalyzer()
