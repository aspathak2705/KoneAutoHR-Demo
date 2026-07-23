from playwright.async_api import Browser, BrowserContext, Page

class BrowserSession:
    def __init__(self, browser: Browser, context: BrowserContext, page: Page):
        self.browser = browser
        self.context = context
        self.page = page

    async def close(self) -> None:
        """
        Gracefully closes the page, context, and browser instance.
        """
        try:
            await self.page.close()
        except Exception:
            pass
        try:
            await self.context.close()
        except Exception:
            pass
        try:
            await self.browser.close()
        except Exception:
            pass
