import pytest
import io
import struct
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from app.modules.induction.parser.media_extractor import extract_mp4_duration, extract_slide_media
from app.modules.presentation.timeline_executor import TimelineExecutor


def create_mock_mvhd_bytes(duration_sec: float = 15.5, timescale: int = 1000) -> bytes:
    duration_val = int(duration_sec * timescale)
    mvhd_payload = b"\x00\x00\x00\x00" + b"\x00" * 4 + b"\x00" * 4 + struct.pack(">II", timescale, duration_val)
    mvhd_atom = struct.pack(">I4s", len(mvhd_payload) + 8, b"mvhd") + mvhd_payload
    moov_atom = struct.pack(">I4s", len(mvhd_atom) + 8, b"moov") + mvhd_atom
    return moov_atom


def test_mp4_duration_extraction_known():
    """Verify that in-memory MP4 parser correctly extracts duration from mvhd box."""
    data = create_mock_mvhd_bytes(24.5)
    duration = extract_mp4_duration(data)
    assert duration == 24.5


def test_mp4_duration_extraction_invalid():
    """Verify that corrupt or non-MP4 payload returns None without throwing exceptions."""
    corrupt_data = b"not an mp4 file content"
    duration = extract_mp4_duration(corrupt_data)
    assert duration is None


def test_media_extractor_with_video_shape(tmp_path):
    """Verify extract_slide_media accurately creates video metadata for MEDIA shape."""
    slide = MagicMock()
    shape = MagicMock()
    shape.shape_type = 16  # MSO_SHAPE_TYPE.MEDIA
    shape.name = "company_culture_video"
    shape.shape_id = 101
    slide.shapes = [shape]
    slide._element = MagicMock()
    slide._element.find.return_value = None  # No special XML timing override -> defaults to automatic

    # Mock relationship blob
    rel = MagicMock()
    rel.reltype = "http://schemas.microsoft.com/office/2007/relationships/media"
    rel.target_part.blob = create_mock_mvhd_bytes(18.0)
    slide.part.rels = {"rId1": rel}

    img_paths, videos = extract_slide_media(slide, 1, tmp_path)
    assert len(videos) == 1
    assert videos[0]["duration"] == 18.0
    assert videos[0]["duration_status"] == "KNOWN"
    assert videos[0]["playback_mode"] == "auto"
    assert videos[0]["supported"] is True


@pytest.mark.asyncio
async def test_timeline_executor_video_synchronization(tmp_path):
    """
    Verify TimelineExecutor holds slide advancement when is_slide_busy is True,
    pausing and resuming narration audio as needed.
    """
    timeline_file = tmp_path / "test_timeline.json"
    timeline_content = """{
        "version": "1.0",
        "duration_ms": 1000,
        "events": [
            {"id": 1, "time_ms": 100, "action": "goto_slide", "slide": 1},
            {"id": 2, "time_ms": 300, "action": "goto_slide", "slide": 2}
        ]
    }"""
    timeline_file.write_text(timeline_content, encoding="utf-8")

    executor = TimelineExecutor(str(timeline_file))

    # Mock audio controller
    audio = MagicMock()
    positions = [50, 150, 350, 400]
    pos_idx = 0

    def mock_position():
        nonlocal pos_idx
        val = positions[min(pos_idx, len(positions) - 1)]
        pos_idx += 1
        return val

    audio.position.side_effect = mock_position
    audio.playing = True

    # Slide 1 is busy with video for 2 iterations
    busy_counter = 2
    current_slide = 1

    def mock_is_slide_busy(slide_num):
        nonlocal busy_counter
        if slide_num == 1 and busy_counter > 0:
            busy_counter -= 1
            return True
        return False

    def mock_get_current_slide():
        return current_slide

    advanced_slides = []

    async def mock_goto_slide(slide_num):
        nonlocal current_slide
        advanced_slides.append(slide_num)
        current_slide = slide_num
        if slide_num == 2:
            audio.playing = False  # End loop after slide 2

    await executor.execute(
        audio_controller=audio,
        on_goto_slide=mock_goto_slide,
        is_slide_busy=mock_is_slide_busy,
        get_current_slide=mock_get_current_slide,
    )

    # Verifications
    assert 1 in advanced_slides
    assert 2 in advanced_slides
    assert audio.pause_audio.called
    assert audio.resume_audio.called


def test_powerpoint_controller_media_methods():
    """Verify PowerPointController exposes media query and play helper signatures without COM crashes."""
    from app.modules.presentation.powerpoint_controller import PowerPointController

    controller = PowerPointController()
    assert hasattr(controller, "get_current_slide_index")
    assert hasattr(controller, "get_slide_media_shapes")
    assert hasattr(controller, "play_media_on_slide")
    assert hasattr(controller, "is_media_playing_on_slide")
    assert controller.get_current_slide_index() == 1
    assert controller.is_media_playing_on_slide(1) is False
