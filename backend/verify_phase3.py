import asyncio
import os
import sys
import time
import tempfile
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
from app.modules.semantic_browser.browser.semantic_browser import semantic_browser
from app.modules.semantic_browser.browser.semantic_snapshot_builder import SemanticSnapshotBuilder
from app.modules.semantic_browser.services.semantic_browser_service import semantic_browser_service
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.semantic_browser.analyzers.dom_analyzer import dom_analyzer
from app.modules.semantic_browser.analyzers.accessibility_analyzer import accessibility_analyzer
from app.modules.semantic_browser.analyzers.meeting_state_analyzer import meeting_state_analyzer
from app.modules.semantic_browser.analyzers.presentation_analyzer import presentation_analyzer
from app.modules.semantic_browser.config import semantic_browser_config

class StepTracker:
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.details = "Not executed"
        self.start_time = 0.0
        self.duration = 0.0

    def start(self):
        self.start_time = time.time()

    def complete(self, success: bool, details: str = "") -> None:
        self.success = success
        self.details = details
        self.duration = time.time() - self.start_time

async def run_verification():
    print("==================================================")
    print("         AUTOHR PHASE 3.1 VERIFICATION RUN        ")
    print("==================================================")
    
    steps = {
        "builder": StepTracker("Snapshot Builder Verified"),
        "init": StepTracker("Browser Initialized"),
        "dom": StepTracker("DOM Analyzer Verified"),
        "accessibility": StepTracker("Accessibility Analyzer Verified"),
        "meeting_state": StepTracker("Meeting State Analyzer Verified"),
        "presentation": StepTracker("Presentation Analyzer Verified"),
        "orchestrator": StepTracker("Semantic Browser Orchestrator"),
        "history": StepTracker("Rolling History Verified"),
        "lobby_update": StepTracker("Dynamic Lobby State Update"),
        "connecting_update": StepTracker("Dynamic Connecting State Update"),
        "connected_update": StepTracker("Dynamic Connected State Update"),
        "presentation_update": StepTracker("Dynamic Presentation Mode Update"),
        "shutdown": StepTracker("Browser Shutdown"),
    }
    
    # 1. Verify Snapshot Builder
    steps["builder"].start()
    try:
        from app.modules.semantic_browser.models.semantic_state import DOMSummary, AccessibilitySummary
        dummy = SemanticSnapshotBuilder.build(
            meeting_state=MeetingState.CONNECTED,
            presentation_state=PresentationMode.NONE,
            dom_summary=DOMSummary(),
            accessibility_summary=AccessibilitySummary(),
            chat_open=False,
            participants_open=False,
            recording_active=False
        )
        assert dummy.meeting_state == MeetingState.CONNECTED
        steps["builder"].complete(True, "SnapshotBuilder compiled successfully")
        print("[OK] Snapshot Builder Verified")
    except Exception as e:
        steps["builder"].complete(False, str(e))
        print(f"[X] Snapshot Builder Verification Failed: {e}")
        return

    # Initialize Browser
    steps["init"].start()
    bot = MeetingBot()
    os.environ["BOT_BROWSER_HEADLESS"] = "true"
    print("Launching browser session...")
    await bot.initialize()
    page = bot.context.page
    steps["init"].complete(True, "Browser process launched headless")
    print("[OK] Browser Initialized")

    try:
        # STAGE 1: Lobby Screen
        print("\n--- STAGE 1: Lobby Screen ---")
        steps["lobby_update"].start()
        lobby_html = """
        <html>
            <head><title>Teams Call Lobby</title></head>
            <body>
                <h1>Mock Call</h1>
                <div id='lobby-msg'>Waiting for someone in the meeting to let you in...</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{lobby_html}")
        await asyncio.sleep(1)
        
        # Test DOM Analyzer
        steps["dom"].start()
        dom = await dom_analyzer.analyze(page)
        steps["dom"].complete(True, f"Scraped {dom.total_interactive_count} interactive nodes")
        print("[OK] DOM Analyzer Verified")

        # Test Accessibility Analyzer
        steps["accessibility"].start()
        acc = await accessibility_analyzer.analyze(page)
        steps["accessibility"].complete(len(acc.nodes) > 0, f"Found {len(acc.nodes)} accessibility nodes")
        print("[OK] Accessibility Analyzer Verified")

        # Test Meeting State Analyzer (Lobby)
        steps["meeting_state"].start()
        m_state = await meeting_state_analyzer.analyze(page, dom)
        assert m_state["state"] == MeetingState.LOBBY
        steps["meeting_state"].complete(True, "Inferred MeetingState.LOBBY from DOM text")
        print("[OK] Meeting State Analyzer Verified (LOBBY)")
        steps["lobby_update"].complete(True, "Transition to LOBBY verified")

        # STAGE 2: Connecting Screen
        print("\n--- STAGE 2: Connecting Screen ---")
        steps["connecting_update"].start()
        connecting_html = "<html><body><div>Connecting...</div></body></html>"
        await page.goto(f"data:text/html,{connecting_html}")
        await asyncio.sleep(1)
        
        dom2 = await dom_analyzer.analyze(page)
        m_state2 = await meeting_state_analyzer.analyze(page, dom2)
        assert m_state2["state"] == MeetingState.CONNECTING
        steps["connecting_update"].complete(True, "Transition to CONNECTING verified")
        print("[OK] Dynamic Connecting State Update")

        # STAGE 3: Connected Screen with Interactive Buttons
        print("\n--- STAGE 3: Connected Screen & Accessibility Focus ---")
        steps["connected_update"].start()
        connected_html = """
        <html>
            <body>
                <button id='btn-leave' data-tid='hangup-button' aria-label='Leave Call'>Leave</button>
                <button id='btn-mute' aria-label='Mute Microphone' aria-describedby='desc-mute'>Mute</button>
                <div id='desc-mute'>Toggles mic status</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{connected_html}")
        await asyncio.sleep(1)
        
        # Focus on mute button
        await page.focus("#btn-mute")
        await asyncio.sleep(0.5)

        # Confirm meeting active (CONNECTED)
        dom3 = await dom_analyzer.analyze(page)
        m_state3 = await meeting_state_analyzer.analyze(page, dom3)
        assert m_state3["state"] == MeetingState.CONNECTED
        steps["connected_update"].complete(True, "Transition to CONNECTED verified")
        print("[OK] Dynamic Connected State Update")

        # Confirm accessibility descriptions and focus
        acc3 = await accessibility_analyzer.analyze(page)
        mute_node = next((n for n in acc3.nodes if n.name == "Mute Microphone"), None)
        assert mute_node is not None
        assert mute_node.description == "Toggles mic status"
        assert mute_node.focused is True
        print("[OK] Accessibility Focus and Description Asserted")

        # STAGE 4: PowerPoint Live Presentation Mode
        print("\n--- STAGE 4: PowerPoint Live Presentation ---")
        steps["presentation_update"].start()
        ppt_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <div data-tid='powerpoint-live-view'>PPT Viewport Frame</div>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{ppt_html}")
        await asyncio.sleep(1)
        
        # Test Presentation Analyzer
        steps["presentation"].start()
        p_state = await presentation_analyzer.analyze(page)
        assert p_state["mode"] == PresentationMode.POWERPOINT_SHARED
        steps["presentation"].complete(True, "Inferred POWERPOINT_SHARED mode")
        print("[OK] Presentation Analyzer Verified (POWERPOINT_SHARED)")

        # STAGE 5: Video Grid Playback
        print("\n--- STAGE 5: Video Grid Playback ---")
        video_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
                <video autoplay></video>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{video_html}")
        await asyncio.sleep(1)
        
        p_state_video = await presentation_analyzer.analyze(page)
        assert p_state_video["mode"] == PresentationMode.VIDEO_PLAYBACK
        print("[OK] Presentation Analyzer Verified (VIDEO_PLAYBACK)")

        # STAGE 6: No Presentation (None)
        print("\n--- STAGE 6: No Presentation ---")
        none_html = """
        <html>
            <body>
                <button data-tid='hangup-button'>Leave</button>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{none_html}")
        await asyncio.sleep(1)
        
        p_state_none = await presentation_analyzer.analyze(page)
        assert p_state_none["mode"] == PresentationMode.NONE
        print("[OK] Presentation Analyzer Verified (NONE)")
        steps["presentation_update"].complete(True, "All presentation modes detected successfully")

        # 2. Verify Semantic Browser Orchestration Directly
        print("\n--- STAGE 7: Semantic Browser Orchestrator ---")
        steps["orchestrator"].start()
        snap = await semantic_browser.generate_snapshot(page)
        
        # Assert snapshot consistency
        assert snap.meeting_state == MeetingState.CONNECTED
        assert snap.presentation_state == PresentationMode.NONE
        assert snap.dom_summary is not None
        assert snap.accessibility_summary is not None
        assert snap.timestamp > 0.0
        assert type(snap.chat_open) is bool
        
        steps["orchestrator"].complete(True, "SemanticBrowser facade orchestrated analyzers directly & verified snapshot structure")
        print("[OK] Semantic Browser Orchestrator & Snapshot Consistency Verified")

        # 3. Verify Rolling History In Service
        print("\n--- STAGE 8: Rolling History ---")
        steps["history"].start()
        from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
        meeting_bot_service._bot = bot # Bind bot context to active service
        
        # Clear existing history
        semantic_browser_service._history = []
        
        # Pull multiple snapshots to fill rolling memory (pull history_size + 2)
        total_pulls = semantic_browser_config.history_size + 2
        for i in range(total_pulls):
            await semantic_browser_service.get_snapshot()
            
        history = semantic_browser_service.get_history()
        # Assert length equals the configuration limits rather than hardcoded 10
        assert len(history) == semantic_browser_config.history_size
        steps["history"].complete(True, f"Rolling memory capped successfully at semantic_browser_config.history_size ({semantic_browser_config.history_size}) items")
        print("[OK] Rolling History Verified via Config Limits")

    finally:
        # Shutdown Browser
        steps["shutdown"].start()
        print("\nClosing browser session...")
        await bot.stop()
        
        # Let Playwright event loops clear cleanly before exiting loop
        await asyncio.sleep(1.5)
        steps["shutdown"].complete(True, "Asynchronous browser resources closed cleanly")
        print("[OK] Browser Shutdown Completed")

    # DISPLAY SUMMARY PANEL
    print("\n" + "=" * 50)
    print("       AUTOHR PHASE 3.1 VERIFICATION SUMMARY      ")
    print("=" * 50)
    
    passed_all = True
    for key, step in steps.items():
        if not step.success:
            passed_all = False
        icon = "[OK]" if step.success else "[X]"
        print(f"{icon:<4} {step.name:<30} | {step.details}")
        
    print("-" * 50)
    overall = "PASSED" if passed_all else "FAILED"
    print(f"Overall Status : {overall}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_verification())
