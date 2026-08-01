import json
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

class TimelineBuilder:
    def build_timeline(
        self,
        session_id: str,
        timestamps: List[Dict[str, Any]],
        total_duration_ms: float,
        slide_count: int,
        session_dir: Path
    ) -> Path:
        """
        Builds the presentation_timeline.json file from voice timestamps.
        Runs internal validations on events order and bounds.
        """
        events = []
        for idx, ts in enumerate(timestamps):
            slide_num = int(ts["slide"])
            time_ms = int(ts["time_ms"])

            # 1. Validation: Slide out of bounds
            if slide_num < 1 or (slide_count > 0 and slide_num > slide_count):
                raise ValueError(f"Timeline validation error: slide {slide_num} is out of bounds (1-{slide_count})")
            
            # 2. Validation: Time out of bounds
            if time_ms < 0 or time_ms > total_duration_ms:
                raise ValueError(f"Timeline validation error: time_ms {time_ms} is out of bounds (0-{total_duration_ms})")

            events.append({
                "id": idx + 1,
                "time_ms": time_ms,
                "action": "goto_slide",
                "slide": slide_num
            })

        # 3. Validation: Ascending order
        for i in range(1, len(events)):
            if events[i]["time_ms"] < events[i-1]["time_ms"]:
                raise ValueError(
                    f"Timeline validation error: event timestamps are not ascending: "
                    f"{events[i]['time_ms']} < {events[i-1]['time_ms']}"
                )

        timeline_data = {
            "version": "1.0",
            "duration_ms": int(total_duration_ms),
            "events": events
        }

        timeline_path = session_dir / "presentation_timeline.json"
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline_data, f, indent=2)

        logger.info(f"TimelineBuilder | Successfully wrote and validated timeline to {timeline_path}")
        return timeline_path

timeline_builder = TimelineBuilder()
