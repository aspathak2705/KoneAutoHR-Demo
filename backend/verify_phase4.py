import asyncio
import os
import sys
import time
from pathlib import Path

# Insert backend dir to path to resolve imports correctly
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Mock environment variables to satisfy app startup configurations
os.environ.setdefault("DATABASE_URL", "sqlite:///./autohr.db")
os.environ.setdefault("UPLOAD_PATH", "./uploads")
os.environ.setdefault("MAX_UPLOAD_SIZE", "52428800")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000")

from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.presentation_observer.observer.presentation_observer import presentation_observer
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.modules.presentation_observer.models.observation_state import ObservationState
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode

class StepTracker:
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.details = "Not executed"

    def complete(self, success: bool, details: str = "") -> None:
        self.success = success
        self.details = details

async def run_verification():
    print("==================================================")
    print("         AUTOHR PHASE 4.3 VERIFICATION RUN        ")
    print("==================================================")
    
    steps = {
        "init": StepTracker("Browser Session Ready"),
        "stage1": StepTracker("Stage 1: Waiting/Lobby (No Pres)"),
        "stage2": StepTracker("Stage 2: PowerPoint Appears (Started)"),
        "stage3": StepTracker("Stage 3: DOM Changes (Slide Changed)"),
        "stage3b": StepTracker("Stage 3B: Identical Content (No Slide Change)"),
        "stage4": StepTracker("Stage 4: Chat Panel Opens (Chat Opened)"),
        "stage5": StepTracker("Stage 5: Roster Panel Opens (Participants Opened)"),
        "stage6": StepTracker("Stage 6: Recording Activates (Recording Started)"),
        "stage7": StepTracker("Stage 7: Presentation Disappears (Ended)"),
        "stage8": StepTracker("Stage 8: Timeline Audit"),
    }
    
    bot = MeetingBot()
    os.environ["BOT_BROWSER_HEADLESS"] = "true"
    await bot.initialize()
    page = bot.context.page
    steps["init"].complete(True, "Browser launched cleanly")
    
    # Bind bot context to meeting bot service for polling pipeline
    from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
    meeting_bot_service._bot = bot
    
    try:
        # STAGE 1: Lobby screen, no presentation
        print("\n--- STAGE 1: Lobby Screen ---")
        lobby_html = "<html><body><div>Waiting for host admission...</div></body></html>"
        await page.goto(f"data:text/html,{lobby_html}")
        await asyncio.sleep(1)
        
        obs1 = await presentation_observer_service.run_observation_cycle()
        assert obs1.observation_state == ObservationState.WAITING
        assert len(obs1.events) == 0
        
        steps["stage1"].complete(True, "Resolved ObservationState.WAITING with zero initial transition events")
        print("[✓] Stage 1 Verified")
        
        # Reset timeline history to clean test start before starting transition stages
        from app.modules.presentation_observer.analyzers.timeline_tracker import timeline_tracker
        timeline_tracker.clear()
        
        # STAGE 2: Admit to meeting and PowerPoint appears
        print("\n--- STAGE 2: Presentation Started ---")
        ppt_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide 1 Content</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{ppt_html}")
        await asyncio.sleep(1)
        
        obs2 = await presentation_observer_service.run_observation_cycle()
        assert ObservationEvent.PRESENTATION_STARTED in obs2.events
        assert obs2.observation_state == ObservationState.ACTIVE
        
        # Verify copied Phase 3 snapshot values and signature presence
        assert obs2.presentation_state == PresentationMode.POWERPOINT_SHARED
        assert obs2.meeting_state == MeetingState.CONNECTED
        assert obs2.timeline_index == 1  # 1 after clearing timeline history
        
        snap2 = semantic_browser_service.get_history()[-1]
        sig2 = snap2.presentation_content_signature
        print(f"  - Stage 2 calculated presentation content signature: {sig2}")
        assert sig2 is not None
        
        # Verify no false positives
        assert ObservationEvent.CHAT_OPENED not in obs2.events
        assert ObservationEvent.RECORDING_STARTED not in obs2.events
        
        steps["stage2"].complete(True, "Resolved PRESENTATION_STARTED, ACTIVE state, and signature presence")
        print("[✓] Stage 2 Verified")
        
        # STAGE 3: Mutate DOM to trigger Slide Change
        print("\n--- STAGE 3: Slide Change ---")
        ppt_slide2 = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide 2 Content</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{ppt_slide2}")
        await asyncio.sleep(1)
        
        obs3 = await presentation_observer_service.run_observation_cycle()
        assert ObservationEvent.SLIDE_CHANGED in obs3.events
        
        snap3 = semantic_browser_service.get_history()[-1]
        sig3 = snap3.presentation_content_signature
        print(f"  - Stage 3 calculated presentation content signature: {sig3}")
        assert sig3 is not None
        assert sig3 != sig2  # Asserts signature changes on content mutation
        
        # Verify context progression
        assert obs3.timestamp >= obs2.timestamp
        assert obs3.timeline_index > obs2.timeline_index
        
        steps["stage3"].complete(True, "Resolved SLIDE_CHANGED event on signature shift")
        print("[✓] Stage 3 Verified")
        
        # STAGE 3B: No Slide Change on identical content
        print("\n--- STAGE 3B: Unchanged Slide Content ---")
        obs3b = await presentation_observer_service.run_observation_cycle()
        assert ObservationEvent.SLIDE_CHANGED not in obs3b.events
        
        snap3b = semantic_browser_service.get_history()[-1]
        assert snap3b.presentation_content_signature == sig3
        
        steps["stage3b"].complete(True, "No SLIDE_CHANGED event emitted when presentation signature remains unchanged")
        print("[✓] Stage 3B Verified")
        
        # STAGE 4: Chat Panel Opens
        print("\n--- STAGE 4: Chat Pane Toggle ---")
        chat_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide 2 Content</div>
                <div data-tid='chat-pane'>Chat Messages Renders Here</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{chat_html}")
        await asyncio.sleep(1)
        
        obs4 = await presentation_observer_service.run_observation_cycle()
        assert ObservationEvent.CHAT_OPENED in obs4.events
        
        # Verify no false positives
        assert ObservationEvent.PRESENTATION_ENDED not in obs4.events
        assert ObservationEvent.RECORDING_STARTED not in obs4.events
        
        steps["stage4"].complete(True, "Resolved CHAT_OPENED event")
        print("[✓] Stage 4 Verified")
        
        # STAGE 5: Participant list pane opens
        print("\n--- STAGE 5: Participants List Toggle ---")
        roster_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide 2 Content</div>
                <div data-tid='chat-pane'>Chat Messages Renders Here</div>
                <div data-tid='participant-list'>Participants names</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{roster_html}")
        await asyncio.sleep(1)
        
        obs5 = await presentation_observer_service.run_observation_cycle()
        assert ObservationEvent.PARTICIPANTS_OPENED in obs5.events
        steps["stage5"].complete(True, "Resolved PARTICIPANTS_OPENED event")
        print("[✓] Stage 5 Verified")
        
        # STAGE 6: Recording activates
        print("\n--- STAGE 6: Recording Activates ---")
        recording_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>Slide 2 Content</div>
                <div data-tid='chat-pane'>Chat Messages Renders Here</div>
                <div data-tid='participant-list'>Participants names</div>
                <div data-tid='recording-indicator'>Recording dot</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{recording_html}")
        await asyncio.sleep(1)
        
        obs6 = await presentation_observer_service.run_observation_cycle()
        assert ObservationEvent.RECORDING_STARTED in obs6.events
        steps["stage6"].complete(True, "Resolved RECORDING_STARTED event")
        print("[✓] Stage 6 Verified")
        
        # STAGE 7: PowerPoint disappears (Presentation Ended)
        print("\n--- STAGE 7: Presentation Ended ---")
        none_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{none_html}")
        await asyncio.sleep(1)
        
        obs7 = await presentation_observer_service.run_observation_cycle()
        assert ObservationEvent.PRESENTATION_ENDED in obs7.events
        assert obs7.observation_state == ObservationState.ENDED
        
        # Verify service caching contains latest observation frame
        latest = presentation_observer_service.get_latest_observation()
        assert latest == obs7
        
        steps["stage7"].complete(True, "Resolved PRESENTATION_ENDED event, ENDED state, and service cache consistency")
        print("[✓] Stage 7 Verified")
        
        # STAGE 8: Timeline Audit
        print("\n--- STAGE 8: Timeline Audit ---")
        timeline = presentation_observer_service.get_timeline()
        print(f"Timeline entries: {[evt.value for evt in timeline]}")
        
        # Assert exact ordering of transition events (excluding lobby WAITING)
        expected = [
            ObservationEvent.PRESENTATION_STARTED,
            ObservationEvent.SLIDE_CHANGED,
            ObservationEvent.CHAT_OPENED,
            ObservationEvent.PARTICIPANTS_OPENED,
            ObservationEvent.RECORDING_STARTED,
            ObservationEvent.PRESENTATION_ENDED
        ]
        assert timeline == expected
        
        steps["stage8"].complete(True, "All transition events registered in correct chronological order")
        print("[✓] Stage 8 Verified")
        
    finally:
        print("\nClosing browser context...")
        await bot.stop()
        await asyncio.sleep(1.5)

    print("\n" + "=" * 50)
    print("       AUTOHR PHASE 4.3 VERIFICATION SUMMARY        ")
    print("=" * 50)
    passed_all = True
    for key, step in steps.items():
        if not step.success:
            passed_all = False
        icon = "[✓]" if step.success else "[X]"
        print(f"{icon:<4} {step.name:<45} | {step.details}")
    print("-" * 50)
    status_str = "PASSED" if passed_all else "FAILED"
    print(f"Overall Status: {status_str}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_verification())
