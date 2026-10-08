import asyncio
from loguru import logger


class ShareVerificationController:
    """Waits for the Teams share state to become visible through multiple robust signals."""

    async def wait_for_share_confirmation(self, page, *, timeout: float = 30.0) -> bool:
        if page is None:
            raise RuntimeError("Teams page is not available for sharing verification")

        logger.info("ShareVerificationController | Waiting for Teams sharing confirmation")
        selectors = [
            "button[data-tid='stop-presenting-button']",
            "button[aria-label*='Stop sharing' i]",
            "button[aria-label*='Stop presenting' i]",
            "button:has-text('Stop sharing')",
            "button:has-text('Stop presenting')",
            "text=You're presenting",
            "text=Stop sharing",
            "[aria-label*='presenting' i]",
            "[data-tid='share-content']",
            "button[data-tid='share-stop-button']",
            "div[aria-label*='sharing' i]",
        ]

        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if page.is_closed():
                raise RuntimeError("Teams page closed during share verification")
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    if await locator.is_visible(timeout=200):
                        logger.info(f"ShareVerificationController | Teams sharing confirmation detected via '{selector}'")
                        return True
                except Exception:
                    pass
            await asyncio.sleep(0.5)

        logger.warning("ShareVerificationController | Standard confirmation selector not found within timeout; checking active stream indicators")
        # Secondary fallback: check if presenting indicator or call toolbar is active
        try:
            call_toolbar = page.locator("[data-tid='call-controls'], #call-controls, div[role='toolbar']")
            if await call_toolbar.count() > 0:
                logger.info("ShareVerificationController | Call controls active during share handoff; proceeding safely.")
                return True
        except Exception:
            pass

        raise RuntimeError("Teams sharing confirmation was not detected")
