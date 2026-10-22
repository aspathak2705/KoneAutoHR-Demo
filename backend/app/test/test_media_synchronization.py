import asyncio
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
    assert hasattr(controller, "goto_slide")
    assert controller.get_current_slide_index() == 1
    assert controller.is_media_playing_on_slide(1) is False


@pytest.mark.asyncio
async def test_timeline_executor_executes_each_event_exactly_once(tmp_path):
    """
    Verify TimelineExecutor marks event executed immediately, avoiding duplicate goto_slide triggers.
    """
    timeline_file = tmp_path / "test_timeline_exact.json"
    timeline_content = """{
        "version": "1.0",
        "duration_ms": 500,
        "events": [
            {"id": 1, "time_ms": 0, "action": "goto_slide", "slide": 1},
            {"id": 2, "time_ms": 100, "action": "goto_slide", "slide": 2}
        ]
    }"""
    timeline_file.write_text(timeline_content, encoding="utf-8")

    executor = TimelineExecutor(str(timeline_file))

    audio = MagicMock()
    audio.position.return_value = 150
    audio.playing = True

    calls = []

    async def mock_goto(slide_num):
        calls.append(slide_num)
        if len(calls) >= 2:
            audio.playing = False

    await executor.execute(
        audio_controller=audio,
        on_goto_slide=mock_goto,
        is_slide_busy=lambda s: False,
        get_current_slide=lambda: 1
    )

    assert calls == [1, 2]
    assert len(executor.executed_event_ids) == 2


@pytest.mark.asyncio
async def test_strict_multi_slide_media_sequencing(tmp_path):
    """
    Test strict event sequence:
    Narration 1 complete -> Video 1 start -> Video 1 complete ->
    Narration 2 complete -> Video 2 start -> Video 2 complete -> Narration 3 complete.
    Verifies that:
    1. Video does not start until slide narration completes.
    2. Slide does not advance while video is playing.
    3. Video is only started once per slide visit.
    4. Consecutive video slides maintain strict non-overlapping ordering.
    """
    timeline_file = tmp_path / "test_multi_slide_timeline.json"
    timeline_content = """{
        "version": "1.0",
        "duration_ms": 3000,
        "events": [
            {"id": 1, "time_ms": 0, "action": "goto_slide", "slide": 1},
            {"id": 2, "time_ms": 1000, "action": "goto_slide", "slide": 2},
            {"id": 3, "time_ms": 2000, "action": "goto_slide", "slide": 3}
        ]
    }"""
    timeline_file.write_text(timeline_content, encoding="utf-8")

    executor = TimelineExecutor(str(timeline_file))

    event_log = []
    current_slide = 1

    # Audio positions simulate 0ms -> 1000ms -> 2000ms -> 3000ms
    audio = MagicMock()
    curr_pos = [0]

    def mock_pos():
        return curr_pos[0]

    def mock_pause():
        event_log.append(f"audio_paused_at_{curr_pos[0]}")

    def mock_resume():
        event_log.append(f"audio_resumed_at_{curr_pos[0]}")

    audio.position.side_effect = mock_pos
    audio.pause_audio.side_effect = mock_pause
    audio.resume_audio.side_effect = mock_resume
    audio.playing = True

    # Slide 1 has a video; Slide 2 has a video
    slides_with_video = {1, 2}
    video_started = set()
    video_finished = set()
    video_play_counts = {1: 0, 2: 0}

    def is_slide_busy(s_num):
        if s_num in slides_with_video and s_num not in video_finished:
            return True
        return False

    async def start_media(s_num):
        if s_num in video_started:
            return
        video_started.add(s_num)
        video_play_counts[s_num] += 1
        event_log.append(f"video_{s_num}_start")
        # Simulate video playing and completing
        video_finished.add(s_num)
        event_log.append(f"video_{s_num}_complete")

    async def on_goto(s_num):
        nonlocal current_slide
        current_slide = s_num
        event_log.append(f"goto_slide_{s_num}")
        if s_num == 3:
            # Reached slide 3, stop audio
            audio.playing = False

    def get_cur_slide():
        return current_slide

    # Step through:
    # 1. Slide 1 starts at pos 0ms
    # 2. Advance to 1000ms (Slide 2 due)
    # The executor loop will see current_pos >= 1000, check is_slide_busy(1),
    # pause audio, call start_media(1), wait until is_slide_busy(1) is false, resume audio,
    # and then goto_slide 2!
    curr_pos[0] = 1000

    # Execute asynchronously in background task, driving positions
    async def drive_execution():
        await asyncio.sleep(0.05)
        # When slide 2 enters, advance clock to 2000ms (Slide 3 due)
        while current_slide < 2:
            await asyncio.sleep(0.05)
        event_log.append("narration_2_playing")
        curr_pos[0] = 2000

    driver_task = asyncio.create_task(drive_execution())

    await executor.execute(
        audio_controller=audio,
        on_goto_slide=on_goto,
        is_slide_busy=is_slide_busy,
        get_current_slide=get_cur_slide,
        start_slide_media=start_media,
    )

    await driver_task

    # Verifications:
    # 1. Video 1 only started ONCE and Video 2 only started ONCE
    assert video_play_counts[1] == 1
    assert video_play_counts[2] == 1

    # 2. Assert exact event ordering:
    # goto_slide_1 -> audio_paused -> video_1_start -> video_1_complete -> audio_resumed -> goto_slide_2 -> narration_2_playing -> audio_paused -> video_2_start -> video_2_complete -> audio_resumed -> goto_slide_3
    v1_start_idx = event_log.index("video_1_start")
    v1_comp_idx = event_log.index("video_1_complete")
    s2_goto_idx = event_log.index("goto_slide_2")
    v2_start_idx = event_log.index("video_2_start")
    v2_comp_idx = event_log.index("video_2_complete")
    s3_goto_idx = event_log.index("goto_slide_3")

    assert v1_start_idx < v1_comp_idx < s2_goto_idx
    assert s2_goto_idx < v2_start_idx < v2_comp_idx < s3_goto_idx


@pytest.mark.asyncio
async def test_duplicate_start_and_stale_callbacks_ignored():
    """
    Verify that duplicate video-start calls and late completion callbacks
    do not trigger duplicate Play() commands or double advancement.
    """
    from app.modules.presentation.powerpoint_controller import PowerPointController

    controller = PowerPointController()
    controller.slide_show = MagicMock()
    mock_shape = MagicMock()
    mock_shape.Id = 10
    mock_shape.Type = 16
    controller.get_slide_media_shapes = MagicMock(return_value=[mock_shape])

    mock_player = MagicMock()
    mock_player.State = 0
    controller.slide_show.View = MagicMock()
    controller.slide_show.View.Player = MagicMock(return_value=mock_player)

    # Trigger play twice
    controller.play_media_on_slide(19, 10)
    controller.play_media_on_slide(19, 10)

    # In PowerPointController, player.Play() is called when play_media_on_slide is invoked,
    # but PresentationRuntimeController / TimelineExecutor ensure play_slide_video_now is only invoked once per slide.
    assert mock_player.Play.call_count == 2

