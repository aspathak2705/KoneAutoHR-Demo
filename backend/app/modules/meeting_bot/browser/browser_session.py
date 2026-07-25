from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page


class BrowserSession:
    def __init__(
        self,
        browser: Optional[Browser],
        context: BrowserContext,
        page: Page,
    ):
        self.browser = browser
        self.context = context
        self.page = page

    async def close(self) -> None:
        """
        Gracefully closes browser resources.
        """

        try:
            await self.page.close()
        except Exception:
            pass

        try:
            await self.context.close()
        except Exception:
            pass

        if self.browser is not None:
            try:
                await self.browser.close()
            except Exception:
                pass