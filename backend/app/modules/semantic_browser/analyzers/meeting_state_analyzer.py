from playwright.async_api import Page
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.semantic_state import DOMSummary
from loguru import logger

class MeetingStateAnalyzer:
    async def analyze(self, page: Page, dom: DOMSummary) -> dict:
        """
        Determines meeting status, active panels, and recording indicators.
        """
        # Default states
        state = MeetingState.DISCONNECTED
        chat_open = False
        participants_open = False
        recording_active = False
        hand_raised = False

        # Gather page title & visible texts
        try:
            title = await page.title()
        except Exception:
            title = ""

        # Fetch actual visible body text directly from page frame to check keywords
        try:
            body_text = await page.locator("body").inner_text()
            body_text = body_text.lower()
        except Exception:
            body_text = ""

        # Check CONNECTED first
        hangup_visible = False
        hangup_selectors = [
            "button[data-tid='hangup-button']",
            "button[aria-label*='Leave' i]",
            "#hangup-button"
        ]
        for sel in hangup_selectors:
            try:
                if await page.locator(sel).is_visible(timeout=500):
                    hangup_visible = True
                    break
            except Exception:
                pass

        if hangup_visible:
            state = MeetingState.CONNECTED
        elif "connecting" in body_text or "connecting" in title.lower():
            state = MeetingState.CONNECTING
        elif any(k in body_text for k in ["let you in", "lobby", "waiting to join", "waiting for host", "admission"]):
            state = MeetingState.LOBBY
        elif "join" in body_text or "meeting" in body_text:
            state = MeetingState.CONNECTING
        else:
            state = MeetingState.DISCONNECTED

        # Panel detection rules
        # Chat pane open
        chat_selectors = [
            "[data-tid='chat-pane']",
            "[aria-label*='chat' i][role='complementary']",
            "div:has-text('Meeting chat')"
        ]
        for sel in chat_selectors:
            try:
                if await page.locator(sel).is_visible(timeout=500):
                    chat_open = True
                    break
            except Exception:
                pass

        # Participants pane open
        roster_selectors = [
            "[data-tid='participant-list']",
            "[aria-label*='people' i][role='complementary']",
            "[aria-label*='participants' i][role='complementary']"
        ]
        for sel in roster_selectors:
            try:
                if await page.locator(sel).is_visible(timeout=500):
                    participants_open = True
                    break
            except Exception:
                pass

        # Recording active indicators
        recording_selectors = [
            "[data-tid='recording-indicator']",
            "[aria-label*='recording' i]",
            ".recording-dot"
        ]
        for sel in recording_selectors:
            try:
                if await page.locator(sel).is_visible(timeout=500):
                    recording_active = True
                    break
            except Exception:
                pass

        # Hand raised indicators
        hand_selectors = [
            "[aria-label*='hand raised' i]",
            "[aria-label*='lower hand' i]"
        ]
        for sel in hand_selectors:
            try:
                if await page.locator(sel).is_visible(timeout=500):
                    hand_raised = True
                    break
            except Exception:
                pass

        status = {
            "state": state,
            "chat_open": chat_open,
            "participants_open": participants_open,
            "recording_active": recording_active,
            "hand_raised": hand_raised
        }
        
        logger.debug(f"MeetingStateAnalyzer | Resolved: {status}")
        return status

meeting_state_analyzer = MeetingStateAnalyzer()
