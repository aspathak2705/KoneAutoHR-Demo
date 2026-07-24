import asyncio
import os
import time
from pathlib import Path
from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.meeting_bot.bot.bot_state import BotState

async def run_verification():
    """
    Phase 2 Verification: Meeting Bot initialization and lifecycle.
    """
    assertions = 0
    start_time = asyncio.get_event_loop().time()
    warnings = []
    
    from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
    bot = meeting_bot_service.get_bot("test-audit-session-p2")
    os.environ["BOT_BROWSER_HEADLESS"] = "true"
    
    try:
        # Initialize Bot
        await bot.initialize()
        assert bot.context.state == BotState.READY, "Bot should be in BotState.READY after initialization"
        assertions += 1
        
        # Verify page is launched
        assert bot.context.page is not None, "Bot Playwright page must be initialized"
        assertions += 1
        
        # Assert chrome details
        assert bot.context.browser_context is not None
        assertions += 1
        
        # Shutdown bot
        await meeting_bot_service.stop_bot("test-audit-session-p2")
        assert bot.context.state == BotState.STOPPED
        assertions += 1
        
    except Exception as e:
        warnings.append(f"Phase 2 verification error: {e}")
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
