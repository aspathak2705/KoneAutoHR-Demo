import asyncio
import os
import time
from pathlib import Path
from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.modules.presentation_observer.models.observation_state import ObservationState
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.semantic_browser.models.presentation_state import PresentationMode

async def run_verification():
    """
    Phase 4 Verification: Presentation Observer & Change Detection.
    """
    assertions = 0
    start_time = asyncio.get_event_loop().time()
    warnings = []
    
    from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
    bot = meeting_bot_service.get_bot("test-audit-session-p4")
    os.environ["BOT_BROWSER_HEADLESS"] = "true"
    
    try:
        await bot.initialize()
        page = bot.context.page
        
        # Clear tracker history
        from app.modules.presentation_observer.analyzers.timeline_tracker import timeline_tracker
        timeline_tracker.clear()

        # 1. Lobby screen, no presentation
        lobby_html = "<html><body><div>Waiting for host admission...</div></body></html>"
        await page.goto(f"data:text/html,{lobby_html}")
        await asyncio.sleep(0.5)
        
        obs1 = await presentation_observer_service.run_observation_cycle("test-audit-session-p4")
        assert obs1.observation_state == ObservationState.WAITING
        assertions += 1
        assert len(obs1.events) == 0
        assertions += 1

        # 2. PowerPoint live appears
        ppt_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide 1 Content: Welcome to KONE Onboarding</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{ppt_html}")
        await asyncio.sleep(0.5)
        
        obs2 = await presentation_observer_service.run_observation_cycle("test-audit-session-p4")
        assert ObservationEvent.PRESENTATION_STARTED in obs2.events
        assertions += 1
        assert obs2.observation_state == ObservationState.ACTIVE
        assertions += 1

        # 3. Slide changes
        ppt_html_2 = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide 2 Content: Safety Guidelines for ESPoo</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{ppt_html_2}")
        await asyncio.sleep(0.5)
        
        obs3 = await presentation_observer_service.run_observation_cycle("test-audit-session-p4")
        assert ObservationEvent.SLIDE_CHANGED in obs3.events
        assertions += 1
        assert obs3.observation_state == ObservationState.ACTIVE
        assertions += 1

        await meeting_bot_service.stop_bot("test-audit-session-p4")
        
    except Exception as e:
        warnings.append(f"Phase 4 verification error: {e}")
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
