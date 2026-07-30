from typing import List, Dict, Optional, Any
import datetime
from playwright.async_api import Page
from loguru import logger

class ChatMonitor:
    def __init__(self):
        self.message_history: List[Dict[str, Any]] = []

    async def get_messages(self, context) -> List[Dict[str, Any]]:
        """
        Scrapes and returns the current list of chat messages from the Teams chat pane.
        """
        page = context.page if hasattr(context, 'page') else context
        if not page:
            return self.message_history

        try:
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
                    logger.info(f"ChatMonitor | Toggling active pane state to: {context.active_pane}")

                if context.active_pane != "chat":
                    return context.chat_messages

            # Attempt to open chat pane if not open
            chat_buttons = [
                "button[data-tid='chat-header-button']",
                "button[aria-label*='chat' i]",
                "button[aria-label*='conversation' i]"
            ]
            
            is_open = False
            if hasattr(context, 'page') and getattr(context, 'current_opened_pane', '') == 'chat':
                is_open = True
                
            if not is_open:
                for btn_sel in chat_buttons:
                    try:
                        btn = page.locator(btn_sel)
                        if await btn.count() > 0:
                            pressed = await btn.first.get_attribute("aria-pressed")
                            if pressed == "true":
                                is_open = True
                                if hasattr(context, 'page'):
                                    context.current_opened_pane = 'chat'
                                break
                    except Exception:
                        pass
                          
            if not is_open:
                for btn_sel in chat_buttons:
                    try:
                        btn = page.locator(btn_sel)
                        if await btn.is_visible(timeout=1000):
                            await btn.click()
                            logger.info("ChatMonitor | Toggled Teams chat pane open.")
                            if hasattr(context, 'page'):
                                context.current_opened_pane = 'chat'
                            break
                    except Exception:
                        pass

            # Extract message elements
            msg_selectors = [
                "div[data-tid='chat-item']",
                "[data-tid='message-body']",
                "div[class*='message-text' i]"
            ]
            
            messages = []
            for sel in msg_selectors:
                try:
                    elements = page.locator(sel)
                    cnt = await elements.count()
                    if cnt > 0:
                        for i in range(cnt):
                            text = await elements.nth(i).inner_text()
                            if text:
                                lines = text.split("\n")
                                sender = "Participant"
                                content = text
                                if len(lines) > 1:
                                    sender = lines[0].strip()
                                    content = " ".join(lines[1:]).strip()
                                
                                messages.append({
                                    "id": f"msg_{i}",
                                    "sender": sender,
                                    "content": content,
                                    "timestamp": datetime.datetime.now().isoformat()
                                })
                        break
                except Exception:
                    pass

            self.message_history = messages
            return messages
        except Exception as e:
            logger.error(f"ChatMonitor | Error scraping messages: {e}")
            return self.message_history

    async def get_unread(self, page: Page) -> List[Dict[str, Any]]:
        """
        Finds messages received after the last known poll.
        """
        old_cnt = len(self.message_history)
        current = await self.get_messages(page)
        return current[old_cnt:]

    async def last_message(self, page: Page) -> Optional[Dict[str, Any]]:
        """
        Returns the last message parsed.
        """
        msgs = await self.get_messages(page)
        return msgs[-1] if msgs else None

chat_monitor = ChatMonitor()
