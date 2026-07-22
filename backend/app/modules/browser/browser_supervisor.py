from loguru import logger
from app.modules.session.runtime_context import RuntimeContext
from app.modules.browser.browser_agent import BrowserAgent

class BrowserSupervisor:
    """
    Browser Supervisor supervising browser launcher states, platform navigation, and lobby status.
    """
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self.agent = BrowserAgent()

    async def join_call(self) -> bool:
        logger.info(f"BrowserSupervisor | Joining call: {self.ctx.meeting_url}")
        launch_res = await self.agent.launch()
        if not launch_res.get("ready"):
            return False

        await self.agent.navigate(self.ctx.meeting_url)
        await self.agent.join_guest(self.ctx.guest_name)
        
        connected = await self.agent.verify_connected()
        self.ctx.update(browser_state="CONNECTED" if connected else "DISCONNECTED")
        return connected

    async def share_screen(self) -> bool:
        shared = await self.agent.share_presentation()
        self.ctx.update(is_presentation_shared=shared)
        return shared

    async def stop_sharing(self) -> None:
        await self.agent.stop_sharing_presentation()
        self.ctx.update(is_presentation_shared=False)

    async def leave_call(self) -> None:
        await self.agent.leave_meeting()
        self.ctx.update(browser_state="DISCONNECTED")
