from loguru import logger
from sqlalchemy.orm import Session as DBSession
from app.modules.session.runtime_context import RuntimeContext
from app.modules.presentation.presentation_adapter import PowerPointPresentationAdapter
from app.modules.assets.asset_manager import asset_manager
from app.modules.presentation.video_controller import VideoController
from app.modules.presentation.verification_engine import VerificationEngine

class PresentationSupervisor:
    """
    Module 4 — Presentation Supervisor (Refactored)
    Supervises only slideshow loading and slide transitions using PowerPointPresentationAdapter.
    """
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self.adapter = PowerPointPresentationAdapter()
        self.video_ctrl = VideoController(ctx.session_id)
        self.verify_engine = VerificationEngine(ctx.session_id)

    async def load_and_start(self, db: DBSession, asset_id: str) -> bool:
        try:
            local_path = asset_manager.resolve(db, asset_id)
            logger.info(f"PresentationSupervisor | Loading asset path: {local_path}")
            success = await self.adapter.open_slideshow(local_path)
            if success:
                self.ctx.update(presentation_asset_id=asset_id)
            return success
        except Exception as e:
            logger.error(f"PresentationSupervisor | Slideshow startup failed: {e}")
            return False

    async def show_slide(self, slide_number: int) -> bool:
        await self.verify_engine.verify_powerpoint_focus()
        success = await self.adapter.go_to_slide(slide_number)
        if success:
            self.ctx.update(current_slide=slide_number)
            await self.verify_engine.verify_slide_number(slide_number)
        return success

    async def play_video(self, url: str, duration: int) -> None:
        await self.video_ctrl.play_video(url)
        await self.video_ctrl.wait_until_finished(duration)

    async def close(self) -> None:
        await self.adapter.close_slideshow()
        logger.info("PresentationSupervisor | PowerPoint slideshow terminated.")
