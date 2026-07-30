from playwright.async_api import Page
from loguru import logger

class ParticipantMonitor:
    async def get_participants(self, context) -> list[str]:
        """
        Scrapes and returns the current participant list from the Teams page DOM.
        Only parses if the meeting call is active.
        """
        page = context.page if hasattr(context, 'page') else context
        if not page:
            return []

        # If call is not active, return empty list
        if not await self.meeting_active(page):
            return []

        import time
        current_time = time.time()
        if hasattr(context, 'page'):
            if not hasattr(context, 'last_pane_toggle_time') or context.last_pane_toggle_time is None:
                context.last_pane_toggle_time = 0.0
            if not hasattr(context, 'active_pane') or context.active_pane is None:
                context.active_pane = "chat"

            if current_time - context.last_pane_toggle_time > 180.0:
                context.active_pane = "roster" if context.active_pane == "chat" else "chat"
                context.last_pane_toggle_time = current_time
                logger.info(f"ParticipantMonitor | Toggling active pane state to: {context.active_pane}")

            if context.active_pane != "roster":
                return context.participants

        # Attempt to open the roster/participants pane if not open
        roster_buttons = [
            "button[data-tid='members-header-button']",
            "button[aria-label*='people' i]",
            "button[aria-label*='participants' i]"
        ]
        
        is_open = False
        if hasattr(context, 'page') and getattr(context, 'current_opened_pane', '') == 'roster':
            is_open = True
            
        if not is_open:
            for btn_sel in roster_buttons:
                try:
                    btn = page.locator(btn_sel)
                    if await btn.count() > 0:
                        pressed = await btn.first.get_attribute("aria-pressed")
                        if pressed == "true":
                            is_open = True
                            if hasattr(context, 'page'):
                                context.current_opened_pane = 'roster'
                            break
                except Exception:
                    pass

        if not is_open:
            for btn_sel in roster_buttons:
                try:
                    btn = page.locator(btn_sel)
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        logger.info("ParticipantMonitor | Toggled participant roster pane open.")
                        if hasattr(context, 'page'):
                            context.current_opened_pane = 'roster'
                        break
                except Exception:
                    pass

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
                            first_line = text.split("\n")[0].strip()
                            if first_line and first_line not in names:
                                names.append(first_line)
                    break
            except Exception:
                pass

        return names

    async def participant_count(self, page: Page) -> int:
        """
        Returns the count of participants.
        """
        names = await self.get_participants(page)
        return len(names)

    async def meeting_active(self, page: Page) -> bool:
        """
        Checks if the call is active.
        True ONLY if call interface toolbars (hangup, layout controls) are loaded on screen.
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
