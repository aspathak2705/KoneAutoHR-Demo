import asyncio
import sys
from typing import Dict, Any, Optional, List
from loguru import logger
from playwright.async_api import Page, async_playwright

from app.modules.browser.perception_engine import perception_engine
from app.modules.browser.state_classifier import state_classifier
from app.modules.browser.action_planner import action_planner
from app.modules.browser.action_executor import action_executor
from app.modules.browser.browser_memory import browser_memory
from app.modules.browser.recovery_engine import recovery_engine
from app.modules.browser.meeting_adapter import TeamsMeetingAdapter, MeetingAdapter
from app.modules.browser.perception_cache import perception_cache
from app.modules.browser.capability_registry import capability_registry
from app.modules.browser.task_planner import task_planner
from app.modules.browser.decision_engine import decision_engine

class BrowserAgent:
    """
    Module 3 — Browser Agent (Teams Web Automation Hardened V4.0)
    Uses pluggable MeetingAdapter, Perception Cache, and Task/Goal Planners.
    """
    def __init__(self, adapter: Optional[MeetingAdapter] = None):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page: Optional[Page] = None
        self._is_launched = False
        
        # Pluggable conference platform adapter
        self.adapter = adapter or TeamsMeetingAdapter()
        capability_registry.register_capabilities(self.adapter.get_supported_capabilities())

    async def launch(self) -> Dict[str, Any]:
        try:
            if sys.platform == "win32":
                try:
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                except Exception:
                    pass

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=[
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-blink-features=AutomationControlled",
                    "--mute-audio",
                    "--disable-features=ExternalProtocolDialog",
                    "--disable-external-intent-requests"
                ]
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                permissions=["microphone", "camera"]
            )
            self._page = await self._context.new_page()
            self._is_launched = True
            browser_memory.update_state("INITIALIZED")
            logger.info("BrowserAgent | AI Browser Agent launched successfully.")
            return {"ready": True, "browser": "chromium"}
        except Exception as e:
            raise RuntimeError(f"BrowserAgent | Launch failure: {str(e)}")

    async def navigate(self, teams_url: str) -> Dict[str, Any]:
        if not self._page or not self._is_launched:
            raise RuntimeError("BrowserAgent | Not launched.")
        try:
            await self._page.goto(teams_url, wait_until="domcontentloaded", timeout=30000)
            browser_memory.meeting_url = teams_url
            logger.info(f"BrowserAgent | Navigated to {teams_url}")
            await asyncio.sleep(2)
            
            # Execute step planning loop
            await self._run_perception_execution_cycle(goal="JOIN_MEETING", guest_name="")
            return {"ready": True, "url": teams_url}
        except Exception as e:
            raise RuntimeError(f"BrowserAgent | Navigation failed: {str(e)}")

    async def join_guest(self, guest_name: str = "KONE AI Trainer") -> Dict[str, Any]:
        if not self._page:
            raise RuntimeError("BrowserAgent | Page context missing.")
        
        logger.info(f"BrowserAgent | Starting join flow for guest: {guest_name}")
        # Run loop until state becomes lobby or meeting
        max_attempts = 10
        for _ in range(max_attempts):
            state = await self._run_perception_execution_cycle(goal="JOIN_MEETING", guest_name=guest_name)
            if state in ["LOBBY", "MEETING"]:
                break
            await asyncio.sleep(2)

        return {"ready": True, "guest_name": guest_name}

    async def verify_connected(self) -> bool:
        if not self._page:
            return False
        perception = await self._perceive_with_cache()
        state = state_classifier.classify(perception)
        browser_memory.update_state(state)
        
        connected = state == "MEETING"
        logger.info(f"BrowserAgent | Connection check status: {state} (connected: {connected})")
        return connected

    async def wait_for_lobby(self) -> Dict[str, Any]:
        # Simple wait check
        await asyncio.sleep(3)
        return {"ready": True}

    async def advance_slide(self) -> bool:
        if not self._page:
            return False
        try:
            # Simulate arrow right to advance slides in active sharing browser context
            await self._page.keyboard.press("ArrowRight")
            logger.info("BrowserAgent | Pressed ArrowRight to advance presentation slide.")
            return True
        except Exception as e:
            logger.error(f"BrowserAgent | Slide advance failure: {e}")
            return False

    async def share_presentation(self) -> bool:
        if not self._page:
            return False
        # Use adapter if screen sharing capability registered
        if capability_registry.supports("ShareScreen"):
            return await self.adapter.share_screen(self._page)
        return False

    async def stop_sharing_presentation(self) -> bool:
        if self._page and capability_registry.supports("ShareScreen"):
            return await self.adapter.stop_sharing(self._page)
        return False

    async def verify_presentation_shared(self) -> bool:
        return browser_memory.is_presentation_shared

    async def leave_meeting(self) -> None:
        if self._page:
            try:
                await self.adapter.leave_meeting(self._page)
            except Exception:
                pass
        
        # Clean shutdown processes
        await self.shutdown()

    async def shutdown(self) -> None:
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._is_launched = False
        logger.info("BrowserAgent | Shutdown processes completed.")

    async def _perceive_with_cache(self) -> Dict[str, Any]:
        # Simple URL + Title signature key
        url = self._page.url
        title = await self._page.title()
        sig = f"{url}:{title}"
        
        cached = perception_cache.get(sig)
        if cached:
            return cached
            
        perception = await perception_engine.perceive(self._page)
        perception_cache.put(sig, perception)
        return perception

    async def _run_perception_execution_cycle(self, goal: str, guest_name: str) -> str:
        # 1. Perceive screen DOM and accessibility using perception cache
        perception = await self._perceive_with_cache()
        
        # 2. Classify state
        state = state_classifier.classify(perception)
        browser_memory.update_state(state)
        logger.info(f"BrowserAgent | Perceived state: {state}")

        # 3. Task Planning Decomposer
        plan_steps = task_planner.plan_goal(goal, {"state": state})
        
        # 4. Plan action
        plan = action_planner.plan(state, goal, guest_name)
        if not plan:
            return state

        # 5. Execute action
        success = await action_executor.execute_action(self._page, plan, perception.get("elements", []))
        if success:
            browser_memory.record_action(plan["action"])
        else:
            await recovery_engine.attempt_recovery(self._page)

        return state
