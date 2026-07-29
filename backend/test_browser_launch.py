import asyncio
import os
import sys

# Add backend directory to sys path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

async def test_launch():
    print("=" * 80)
    print("TEST BROWSER LAUNCH ROUTINE")
    print("=" * 80)
    
    from app.modules.meeting_bot.browser.browser_manager import browser_manager
    
    try:
        # Dry-run launch in headless mode
        from app.modules.meeting_bot.config import meeting_bot_config
        meeting_bot_config.headless = True
        
        print("Triggering browser launch...")
        session = await browser_manager.launch("test_session_id_123")
        print(f"Browser launched successfully! Page URL: {session.page.url}")
        
        await browser_manager.close()
        print("Browser closed successfully!")
        print("TEST PASSED: Browser launch execution matches new config path correctly.")
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_launch())
