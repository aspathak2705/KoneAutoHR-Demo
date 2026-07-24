import asyncio
import os
import time
from pathlib import Path
from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.semantic_browser.services.semantic_browser_service import semantic_browser_service
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode

async def run_verification():
    """
    Phase 3 Verification: Semantic Browser Scraping & DOM Summarizer.
    """
    assertions = 0
    start_time = asyncio.get_event_loop().time()
    warnings = []
    
    from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
    bot = meeting_bot_service.get_bot("test-audit-session-p3")
    os.environ["BOT_BROWSER_HEADLESS"] = "true"
    
    try:
        await bot.initialize()
        page = bot.context.page

        # 1. Lobby Screen
        lobby_html = "<html><body><div>Waiting for host admission...</div></body></html>"
        await page.goto(f"data:text/html,{lobby_html}")
        await asyncio.sleep(0.5)
        
        snap1 = await semantic_browser_service.get_snapshot("test-audit-session-p3")
        assert snap1.meeting_state == MeetingState.LOBBY
        assertions += 1
        assert snap1.presentation_state == PresentationMode.NONE
        assertions += 1
        
        # 2. PowerPoint Sharing Started
        ppt_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide Content: Innovation KONE</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{ppt_html}")
        await asyncio.sleep(0.5)
        
        snap2 = await semantic_browser_service.get_snapshot("test-audit-session-p3")
        assert snap2.meeting_state == MeetingState.CONNECTED
        assertions += 1
        assert snap2.presentation_state == PresentationMode.POWERPOINT_SHARED
        assertions += 1
        assert snap2.presentation_content_signature is not None
        assertions += 1

        # Clean up
        await meeting_bot_service.stop_bot("test-audit-session-p3")
        
    except Exception as e:
        warnings.append(f"Phase 3 verification error: {e}")
        return {
            "success": False,
            "assertions": assertions,
            "duration_ms": (asyncio.get_event_loop().time() - start_time) * 1000,
            "warnings": warnings
        }
        
    duration = (asyncio.get_event_loop().time() - start_time) * 1000 # ms
    return {
        "success": True,
        "assertions": assertions,
        "duration_ms": duration,
        "warnings": warnings
    }
