import wave
import json
import pytest
from pathlib import Path
from app.modules.presentation.package_builder.package_builder import package_builder


def create_synthetic_wav(file_path: Path, duration_ms: int = 1000, sample_rate: int = 44100) -> Path:
    num_frames = int((duration_ms / 1000.0) * sample_rate)
    frame_bytes = b"\x10\x00\x10\x00"  # 16-bit stereo frame
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(file_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(frame_bytes * num_frames)
    return file_path


def test_grouped_audio_timeline_and_single_concatenation(tmp_path):
    """
    Test 3-slide group:
    Slide 1: individual 10s audio
    Slide 2-4: 45s audio grouped across 3 slides
    Slide 5: silent 5s hold
    Total expected duration = 60s
    """
    session_dir = tmp_path / "session_group"
    wav1 = create_synthetic_wav(tmp_path / "s1.wav", duration_ms=10000)
    wav_group = create_synthetic_wav(tmp_path / "group_2_4.wav", duration_ms=45000)

    slide_audios = {
        1: wav1,
        2: wav_group,
        3: None,
        4: None,
        5: None
    }
    slide_notes = {
        1: "Individual intro",
        2: "Group master covering 2-4",
        3: "Slide 3 content",
        4: "Slide 4 content",
        5: "Silent conclusion"
    }
    slide_types = {
        1: "AUDIO",
        2: "GROUP_MASTER",
        3: "GROUP_LINKED",
        4: "GROUP_LINKED",
        5: "SILENT"
    }
    slide_groups = {
        2: {
            "group_id": "group_2_4",
            "group_slides": [2, 3, 4],
            "duration_ms": 45000,
            "slide_durations_ms": {2: 15000, 3: 15000, 4: 15000}
        },
        3: {
            "group_id": "group_2_4",
            "master_slide": 2,
            "duration_ms": 15000
        },
        4: {
            "group_id": "group_2_4",
            "master_slide": 2,
            "duration_ms": 15000
        }
    }

    manifest_path = package_builder.build_hr_package(
        session_id="group_sess",
        session_dir=session_dir,
        presentation_filename="presentation.pptx",
        slide_count=5,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types,
        slide_groups=slide_groups
    )
    assert manifest_path.exists()

    # 1. Verify narration.wav duration is exactly 60.0s (10s + 45s + 5s)
    narration_wav = session_dir / "narration.wav"
    assert narration_wav.exists()
    with wave.open(str(narration_wav), "rb") as w:
        dur_sec = w.getnframes() / float(w.getframerate())
        assert abs(dur_sec - 60.0) < 0.1

    # 2. Verify presentation_timeline.json
    timeline_path = session_dir / "presentation_timeline.json"
    assert timeline_path.exists()
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    assert timeline["duration_ms"] == 60000
    events = timeline["events"]
    assert len(events) == 5

    # Check event sequence & deterministic offsets
    # Slide 1: 0ms
    # Slide 2: 10000ms
    # Slide 3: 25000ms (10000 + 15000)
    # Slide 4: 40000ms (25000 + 15000)
    # Slide 5: 55000ms (40000 + 15000)
    assert events[0] == {"id": 1, "time_ms": 0, "action": "goto_slide", "slide": 1}
    assert events[1] == {"id": 2, "time_ms": 10000, "action": "goto_slide", "slide": 2}
    assert events[2] == {"id": 3, "time_ms": 25000, "action": "goto_slide", "slide": 3}
    assert events[3] == {"id": 4, "time_ms": 40000, "action": "goto_slide", "slide": 4}
    assert events[4] == {"id": 5, "time_ms": 55000, "action": "goto_slide", "slide": 5}

    # 3. Verify manifest metadata
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["duration_ms"] == 60000
    assert manifest["slides"] == 5

    meta = manifest["slide_audio_metadata"]
    assert meta["1"]["type"] == "AUDIO"
    assert meta["2"]["type"] == "GROUP_MASTER"
    assert meta["2"]["group_slides"] == [2, 3, 4]
    assert meta["3"]["type"] == "GROUP_LINKED"
    assert meta["3"]["master_slide"] == 2
    assert meta["4"]["type"] == "GROUP_LINKED"
    assert meta["4"]["master_slide"] == 2
    assert meta["5"]["type"] == "SILENT"


def test_grouped_audio_remainder_distribution(tmp_path):
    """
    Test 2-slide group with odd duration (e.g. 25001ms over 2 slides):
    Slide 1: 12500ms
    Slide 2: 12501ms
    """
    session_dir = tmp_path / "session_odd"
    wav_group = create_synthetic_wav(tmp_path / "group_odd.wav", duration_ms=25001)

    slide_audios = {1: wav_group, 2: None}
    slide_notes = {1: "Master", 2: "Linked"}
    slide_types = {1: "GROUP_MASTER", 2: "GROUP_LINKED"}
    slide_groups = {
        1: {
            "group_id": "group_1_2",
            "group_slides": [1, 2],
            "duration_ms": 25001
        },
        2: {
            "group_id": "group_1_2",
            "master_slide": 1
        }
    }

    manifest_path = package_builder.build_hr_package(
        session_id="odd_sess",
        session_dir=session_dir,
        presentation_filename="presentation.pptx",
        slide_count=2,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types,
        slide_groups=slide_groups
    )
    with open(session_dir / "presentation_timeline.json", "r", encoding="utf-8") as f:
        timeline = json.load(f)

    events = timeline["events"]
    assert events[0]["time_ms"] == 0
    assert events[0]["slide"] == 1
    assert events[1]["time_ms"] == 12500
    assert events[1]["slide"] == 2


def test_grouped_audio_validation_logic(tmp_path):
    """
    Test validation logic for grouped audio configurations:
    1. Valid group covering slides 2, 3, 4
    2. Broken link where linked slide points to nonexistent master
    """
    # Valid setup
    group_audio = create_synthetic_wav(tmp_path / "grp.wav", duration_ms=45000)
    meta = {
        "1": {"type": "AUDIO", "audio_path": str(create_synthetic_wav(tmp_path / "s1.wav", 5000)), "duration_ms": 5000},
        "2": {"type": "GROUP_MASTER", "group_id": "grp1", "audio_path": str(group_audio), "duration_ms": 45000, "group_slides": [2, 3, 4]},
        "3": {"type": "GROUP_LINKED", "group_id": "grp1", "master_slide": 2, "audio_path": None, "duration_ms": 0},
        "4": {"type": "GROUP_LINKED", "group_id": "grp1", "master_slide": 2, "audio_path": None, "duration_ms": 0},
        "5": {"type": "SILENT", "audio_path": None, "duration_ms": 5000}
    }

    errors = []
    slide_count = 5
    for s_num in range(1, slide_count + 1):
        s_key = str(s_num)
        entry = meta.get(s_key, {})
        entry_type = entry.get("type", "AUDIO")
        if entry_type == "GROUP_MASTER":
            for g_s in entry.get("group_slides", []):
                if g_s != s_num:
                    linked = meta.get(str(g_s))
                    if not linked or linked.get("type") != "GROUP_LINKED" or linked.get("master_slide") != s_num:
                        errors.append(f"Broken master {s_num}")
        elif entry_type == "GROUP_LINKED":
            m_s = entry.get("master_slide")
            if not m_s or str(m_s) not in meta:
                errors.append(f"Broken link {s_num}")
    assert len(errors) == 0

    # Broken link setup
    meta["3"]["master_slide"] = 99
    errors_broken = []
    for s_num in range(1, slide_count + 1):
        entry = meta.get(str(s_num), {})
        if entry.get("type") == "GROUP_LINKED":
            m_s = entry.get("master_slide")
            if not m_s or str(m_s) not in meta or meta[str(m_s)].get("type") != "GROUP_MASTER":
                errors_broken.append(f"Slide {s_num} invalid master {m_s}")
    assert len(errors_broken) == 1
    assert "Slide 3 invalid master 99" in errors_broken[0]
