import asyncio
from typing import Dict, Any, Callable, List, Optional
from loguru import logger


class TimelineExecutor:
    def __init__(self, timeline_path: str):
        import json
        with open(timeline_path, "r", encoding="utf-8") as f:
            self.timeline = json.load(f)

        # Sort events by time_ms ascending
        self.events = sorted(self.timeline.get("events", []), key=lambda x: x.get("time_ms", 0))
        self.executed_event_ids = set()

    async def execute(
        self,
        audio_controller,
        on_goto_slide: Callable[[int], Any],
        is_slide_busy: Optional[Callable[[int], bool]] = None,
        get_current_slide: Optional[Callable[[], int]] = None,
        start_slide_media: Optional[Callable[[int], Any]] = None,
    ) -> None:
        """
        Executes events matching the active audio playback time offset.
        If a slide has active media playing (is_slide_busy returns True), pauses
        narration audio and delays the next slide event until the media completes.
        """
        logger.info("TimelineExecutor | Starting timeline execution loop.")
        
        while audio_controller.playing or (is_slide_busy and get_current_slide and is_slide_busy(get_current_slide())):
            current_pos = audio_controller.position()

            # Find and execute all due events
            for event in self.events:
                event_id = event["id"]
                if event_id in self.executed_event_ids:
                    continue

                if current_pos >= event["time_ms"]:
                    slide_num = event.get("slide")
                    action = event.get("action")

                    # Check if previous slide is still busy playing a video before advancing
                    if is_slide_busy and get_current_slide:
                        cur_slide = get_current_slide()
                        if cur_slide != slide_num and is_slide_busy(cur_slide):
                            logger.info(
                                f"TimelineExecutor | Slide {cur_slide} narration completed. "
                                f"Holding timeline progression before entering Slide {slide_num}..."
                            )
                            # Temporarily pause narration stream so narration does not skip ahead
                            audio_controller.pause_audio()
                            
                            # Authoritatively trigger embedded video on cur_slide if not already started
                            if start_slide_media:
                                if asyncio.iscoroutinefunction(start_slide_media):
                                    try:
                                        await start_slide_media(cur_slide, trigger_source="timeline_narration_complete")
                                    except TypeError:
                                        await start_slide_media(cur_slide)
                                else:
                                    try:
                                        start_slide_media(cur_slide, trigger_source="timeline_narration_complete")
                                    except TypeError:
                                        start_slide_media(cur_slide)

                            while is_slide_busy(cur_slide):
                                await asyncio.sleep(0.3)
                            logger.info(f"TimelineExecutor | Slide {cur_slide} media completed. Resuming narration audio.")
                            # Resynchronize current_pos after pause/resume cycle
                            current_pos = audio_controller.position()
                            audio_controller.resume_audio()

                    self.executed_event_ids.add(event_id)

                    if action == "goto_slide":
                        logger.info(
                            f"TimelineExecutor | Triggering event {event_id}: goto_slide {slide_num} "
                            f"at position {current_pos:.0f}ms (scheduled {event['time_ms']}ms)"
                        )
                        try:
                            if asyncio.iscoroutinefunction(on_goto_slide):
                                await on_goto_slide(slide_num)
                            else:
                                on_goto_slide(slide_num)
                        except Exception as e:
                            logger.error(f"TimelineExecutor | Event handler failed: {e}")

            await asyncio.sleep(0.1)

        # Post-loop verification: ensure last slide video also completes
        if is_slide_busy and get_current_slide:
            cur_slide = get_current_slide()
            if is_slide_busy(cur_slide):
                logger.info(f"TimelineExecutor | Waiting for final slide {cur_slide} video to complete...")
                if start_slide_media:
                    if asyncio.iscoroutinefunction(start_slide_media):
                        try:
                            await start_slide_media(cur_slide, trigger_source="final_slide_post_loop")
                        except TypeError:
                            await start_slide_media(cur_slide)
                    else:
                        try:
                            start_slide_media(cur_slide, trigger_source="final_slide_post_loop")
                        except TypeError:
                            start_slide_media(cur_slide)
                while is_slide_busy(cur_slide):
                    await asyncio.sleep(0.3)

        logger.info("TimelineExecutor | Timeline execution loop completed.")
