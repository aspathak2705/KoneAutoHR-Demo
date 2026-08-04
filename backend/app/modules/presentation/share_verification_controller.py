from loguru import logger


class ShareVerificationController:
    """Waits for the Teams share state to become visible through multiple signals."""

    async def wait_for_share_confirmation(self, page, *, timeout: float = 60.0) -> bool:
        if page is None:
            raise RuntimeError("Teams page is not available for sharing verification")

        logger.info("ShareVerificationController | Waiting for Teams sharing confirmation")
        selectors = [
            "button[data-tid='stop-presenting-button']",
            "button[aria-label*='Stop sharing' i]",
            "button[aria-label*='Stop presenting' i]",
            "button:has-text('Stop sharing')",
            "text=You're presenting",
            "[aria-label*='presenting' i]",
            "[data-tid='share-content']",
            "button[data-tid='share-stop-button']",
        ]

        deadline = __import__("asyncio").get_running_loop().time() + timeout
        while __import__("asyncio").get_running_loop().time() < deadline:
            if page.is_closed():
                raise RuntimeError("Teams page closed during share verification")
            for selector in selectors:
                try:
                    if await page.locator(selector).first.is_visible(timeout=200):
                        logger.info("ShareVerificationController | Teams sharing confirmation detected")
                        return True
                except Exception:
                    pass
            await __import__("asyncio").sleep(0.5)

        raise RuntimeError("Teams sharing confirmation was not detected")
        if page is None:
            raise RuntimeError("Teams page is not available for sharing verification")

        logger.info("ShareVerificationController | Waiting for Teams sharing confirmation")
        selectors = [
            "button[data-tid='stop-presenting-button']",
            "button[aria-label*='Stop sharing' i]",
            "button:has-text('Stop sharing')",
            "text=You're presenting",
            "[aria-label*='presenting' i]",
            "[data-tid='share-content']",
            "button[data-tid='share-stop-button']",  # additional fallback
        ]

        deadline = __import__("asyncio").get_running_loop().time() + timeout
        while __import__("asyncio").get_running_loop().time() < deadline:
            if page.is_closed():
                raise RuntimeError("Teams page closed during share verification")
            for selector in selectors:
                try:
                    if await page.locator(selector).first.is_visible(timeout=200):
                        logger.info("ShareVerificationController | Teams sharing confirmation detected")
                        return True
                except Exception:
                    pass
            await __import__("asyncio").sleep(0.5)

        raise RuntimeError("Teams sharing confirmation was not detected")
        if page is None:
            raise RuntimeError("Teams page is not available for sharing verification")

        logger.info("ShareVerificationController | Waiting for Teams sharing confirmation")
        selectors = [
            "button[data-tid='stop-presenting-button']",
            "button[aria-label*='Stop sharing' i]",
            "button:has-text('Stop sharing')",
            "text=You're presenting",
            "[aria-label*='presenting' i]",
            "[data-tid='share-content']",
        ]

        deadline = __import__("asyncio").get_running_loop().time() + timeout
        while __import__("asyncio").get_running_loop().time() < deadline:
            if page.is_closed():
                raise RuntimeError("Teams page closed during share verification")
            for selector in selectors:
                try:
                    if await page.locator(selector).first.is_visible(timeout=200):
                        logger.info("ShareVerificationController | Teams sharing confirmation detected")
                        return True
                except Exception:
                    pass
            await __import__("asyncio").sleep(0.5)

        raise RuntimeError("Teams sharing confirmation was not detected")
