import asyncio
from typing import Dict, Any, Callable, List
from loguru import logger

class TimelineExecutor:
    def __init__(self, timeline_path: str):
        import json
        with open(timeline_path, "r", encoding="utf-8") as f:
            self.timeline = json.load(f)
        
        # Sort events by time_ms ascending
        self.events = sorted(self.timeline.get("events", []), key=lambda x: x.get("time_ms", 0))
        self.executed_event_ids = set()

    async def execute(self, audio_controller, on_goto_slide: Callable[[int], Any]) -> None:
        """
        Executes events matching the active audio playback time offset.
        """
        logger.info("TimelineExecutor | Starting timeline execution loop.")
        while audio_controller.playing:
            current_pos = audio_controller.position()
            
            # Find and execute all due events
            for event in self.events:
                event_id = event["id"]
                if event_id in self.executed_event_ids:
                    continue
                    
                if current_pos >= event["time_ms"]:
                    action = event.get("action")
                    if action == "goto_slide":
                        slide_num = event.get("slide")
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
                    
                    self.executed_event_ids.add(event_id)
            
            await asyncio.sleep(0.1)
        logger.info("TimelineExecutor | Timeline execution loop completed.")
