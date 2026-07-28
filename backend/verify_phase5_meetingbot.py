import asyncio
import sys
from loguru import logger
from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.meeting_bot.bot.bot_state import BotState
from app.modules.meeting_bot.teams.teams_controller import teams_controller

async def run_meeting_bot_verification():
    logger.info("==================================================")
    logger.info("     AUTOHR MEETING BOT E2E VERIFICATION RUN      ")
    logger.info("==================================================")

    # Initialize Bot instance
    bot = MeetingBot(session_id="verification_session")
    
    # Stub set_state to avoid database mapper initialization errors during standalone execution
    def mock_set_state(state):
        logger.info(f"Mocked set_state: {state}")
        bot.context.state = state
    bot.set_state = mock_set_state
    
    try:
        # Step 1: Launch Browser
        logger.info("--- STAGE 1: Browser Launch ---")
        from app.modules.meeting_bot.browser.browser_manager import browser_manager
        browser_session = await browser_manager.launch("verification_session")
        bot.context.browser = browser_session.browser
        bot.context.browser_context = browser_session.context
        bot.context.page = browser_session.page
        
        await bot.initialize()
        if bot.context.state != BotState.READY:
            raise RuntimeError(f"Bot failed to initialize to READY. Current: {bot.context.state}")
        logger.info("[OK] Browser Launched successfully and Bot is READY")

        # Step 2: Open meeting & Bypassing Launcher
        logger.info("--- STAGE 2: Navigate and Continue ---")
        test_meeting_url = "https://teams.live.com/meet/9313333239802?p=4GaDhFN3XNQiTFTNSt"
        bot.context.page = await teams_controller.open_meeting(bot.context.page, test_meeting_url)
        logger.info("[OK] Navigation complete and launcher bypassed")

        # Step 3: SPA pre-join checks
        logger.info("--- STAGE 3: Pre-join Loading Verification ---")
        bot.context.page = await teams_controller.wait_for_prejoin(bot.context.page)
        logger.info("[OK] Pre-join SPA rendered successfully")

        # Step 4: Configure Devices
        logger.info("--- STAGE 4: Device Configuration ---")
        device_res = await teams_controller.configure_devices(bot.context.page, mute_mic=True, turn_off_cam=True)
        logger.info(f"[OK] Device configuration completed: {device_res.message}")

        # Step 5: Name Entry & Submit Join
        logger.info("--- STAGE 5: Name Entry & Join Submission ---")
        await teams_controller.enter_name_and_join(bot.context.page, "KONE AI Verification Bot")
        logger.info("[OK] Display name entered and guest request submitted successfully")

        # Step 6: Leave Meeting
        logger.info("--- STAGE 6: Clean Leave and Disconnect ---")
        await teams_controller.leave_meeting(bot.context.page)
        logger.info("[OK] Meeting left cleanly")

        logger.info("==================================================")
        logger.info("   MEETING BOT VERIFICATION SUMMARY: PASSED       ")
        logger.info("==================================================")
        
    except Exception as err:
        logger.error("==================================================")
        logger.error(f"  MEETING BOT VERIFICATION SUMMARY: FAILED: {err}")
        logger.error("==================================================")
        sys.exit(1)
        
    finally:
        # Clean shutdown of browser context
        if bot.context.browser_context:
            await bot.context.browser_context.close()
        if bot.context.browser:
            await bot.context.browser.close()

if __name__ == "__main__":
    asyncio.run(run_meeting_bot_verification())
