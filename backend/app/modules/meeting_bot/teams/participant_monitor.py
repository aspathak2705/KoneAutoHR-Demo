from playwright.async_api import Page
from loguru import logger

class ParticipantMonitor:
    async def get_participants(self, page: Page) -> list[str]:
        """
        Scrapes and returns the current participant list from the Teams page DOM.
        """
        # Attempt to open the roster/participants pane if not open
        roster_buttons = [
            "button[data-tid='members-header-button']",
            "button[aria-label*='people' i]",
            "button[aria-label*='participants' i]"
        ]
        
        # Check if roster panel is already open
        is_open = await page.locator("div[role='listitem']").count() > 0
        if not is_open:
            for btn_sel in roster_buttons:
                try:
                    btn = page.locator(btn_sel)
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        logger.info("ParticipantMonitor | Toggled participant roster pane open.")
                        break
                except Exception:
                    pass

        # Parse participant item elements
        item_selectors = [
            "[data-tid='participant-list-item']",
            "div[role='listitem']",
            "div[data-cid='roster-participant']"
        ]
        
        names = []
        for sel in item_selectors:
            try:
                elements = page.locator(sel)
                cnt = await elements.count()
                if cnt > 0:
                    for i in range(cnt):
                        text = await elements.nth(i).inner_text()
                        if text:
                            # Normalize text
                            first_line = text.split("\n")[0].strip()
                            if first_line and first_line not in names:
                                names.append(first_line)
                    break
            except Exception:
                pass

        return names or ["KONE AI Bot (You)"]

    async def participant_count(self, page: Page) -> int:
        """
        Returns the count of participants.
        """
        names = await self.get_participants(page)
        return len(names)

    async def meeting_active(self, page: Page) -> bool:
        """
        Checks if the call is active.
        """
        active_selectors = [
            "button[data-tid='hangup-button']",
            "button[aria-label*='Leave' i]",
            "#hangup-button",
            "[data-tid='calling-screen']"
        ]
        for sel in active_selectors:
            try:
                if await page.locator(sel).is_visible(timeout=1000):
                    return True
            except Exception:
                pass
        return False

participant_monitor = ParticipantMonitor()
