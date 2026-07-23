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
from app.modules.semantic_browser.browser.semantic_browser import semantic_browser
from app.modules.semantic_browser.browser.semantic_snapshot_builder import SemanticSnapshotBuilder
from app.modules.semantic_browser.services.semantic_browser_service import semantic_browser_service
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode

async def run_verification():
    print("==================================================")
    print("         AUTOHR PHASE 3.1 VERIFICATION RUN        ")
    print("==================================================")
    
    # 1. Test Snapshot Builder Factory
    print("Testing SemanticSnapshotBuilder instantiation...")
    from app.modules.semantic_browser.models.semantic_state import DOMSummary, AccessibilitySummary
    dummy_snap = SemanticSnapshotBuilder.build(
        meeting_state=MeetingState.CONNECTED,
        presentation_state=PresentationMode.NONE,
        dom_summary=DOMSummary(),
        accessibility_summary=AccessibilitySummary(),
        chat_open=True,
        participants_open=False,
        recording_active=True
    )
    assert dummy_snap.meeting_state == MeetingState.CONNECTED
    assert dummy_snap.chat_open is True
    print("[✓] Step 1: Snapshot Builder verified")

    bot = MeetingBot()
    os.environ["BOT_BROWSER_HEADLESS"] = "true"
    
    print("Initializing browser session...")
    await bot.initialize()
    
    try:
        page = bot.context.page
        print("Navigating to static HTML page...")
        mock_html = """
        <html>
            <head><title>Teams Meeting Test</title></head>
            <body>
                <h1>Mock Call Stage</h1>
                <button id='btn-mute' aria-label='Mute Microphone'>Mute</button>
                <form id='test-form'>
                    <input id='name-input' placeholder='Guest Name' value='Verification Test'/>
                </form>
                <div role='dialog' aria-label='Consent Dialog'>Modal Prompt</div>
                
                <!-- Mock active screen share video -->
                <video aria-label='Screen sharing video stream' style='width:640px;height:480px;' autoplay></video>
            </body>
        </html>
        """
        await page.goto(f"data:text/html,{mock_html}")
        await asyncio.sleep(2)
        
        # Test DOM Analyzer Region Scanning
        print("Executing DOM Analyzer...")
        from app.modules.semantic_browser.analyzers.dom_analyzer import dom_analyzer
        dom = await dom_analyzer.analyze(page)
        dialog_elements = [el for el in dom.elements if el.role == "dialog" or el.tag == "form"]
        print(f"[✓] DOM Analyzer compiled {dom.total_interactive_count} interactive elements (Found {len(dialog_elements)} modals/forms)")
        for el in dom.elements:
            print(f"  - Element: tag={el.tag}, id={el.id}, role={el.role}, label={el.label}")
            
        # Test Service rolling history list
        print("Polling semantic browser snapshots to verify rolling history...")
        # Bind page reference inside bot service to test semantic_browser_service
        from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
        # Setup bot instance in service
        meeting_bot_service._bot = bot
        
        # Pull multiple snapshots
        for i in range(3):
            await semantic_browser_service.get_snapshot()
            await asyncio.sleep(0.1)
            
        history = semantic_browser_service.get_history()
        print(f"[✓] Rolling snapshot history verified. History size: {len(history)} (Max: 10)")
        assert len(history) == 3
        
        # Test state change updates (mutate DOM and poll again)
        print("Mutating DOM dynamically to verify snapshot updates...")
        await page.evaluate("document.getElementById('btn-mute').setAttribute('aria-label', 'Unmute Microphone')")
        
        new_snap = await semantic_browser_service.get_snapshot()
        mute_button = next((el for el in new_snap.dom_summary.elements if el.id == "btn-mute"), None)
        print(f"  - Updated element label: {mute_button.label if mute_button else 'None'}")
        assert mute_button is not None and mute_button.label == "Unmute Microphone"
        print("[✓] Step 5: Snapshot updates dynamically on state shifts")
        
    finally:
        print("Closing browser session...")
        await bot.stop()
        await asyncio.sleep(1)
        
    print("==================================================")
    print("     Phase 3.1 Verification Successful. [✓]       ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_verification())
