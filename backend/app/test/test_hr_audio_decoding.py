import wave
import json
import pytest
from pathlib import Path
import numpy as np
import soundfile as sf
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


def create_synthetic_mp3(file_path: Path, duration_ms: int = 1000, sample_rate: int = 44100) -> Path:
    num_frames = int((duration_ms / 1000.0) * sample_rate)
    data = np.zeros((num_frames, 2), dtype=np.float32)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(file_path), data, sample_rate, format="MP3")
    return file_path


def test_decode_valid_mp3_to_canonical_wav(tmp_path):
    mp3_file = create_synthetic_mp3(tmp_path / "test.mp3", duration_ms=2000, sample_rate=48000)
    out_wav = tmp_path / "decoded.wav"

    dur_ms = package_builder.convert_to_canonical_wav(mp3_file, out_wav)
    assert out_wav.exists()
    assert abs(dur_ms - 2000.0) < 50.0  # MP3 frame boundary tolerance

    # Inspect WAV parameters
    params = package_builder.get_wav_params(out_wav)
    assert params.framerate == 44100
    assert params.nchannels == 2
    assert params.sampwidth == 2


def test_reject_empty_and_corrupted_audio(tmp_path):
    empty_file = tmp_path / "empty.mp3"
    empty_file.write_bytes(b"")

    with pytest.raises(ValueError, match="empty"):
        package_builder.convert_to_canonical_wav(empty_file, tmp_path / "out1.wav")

    corrupted_file = tmp_path / "corrupt.mp3"
    corrupted_file.write_bytes(b"NOT_A_REAL_MP3_OR_WAV_HEADER_DATA")

    with pytest.raises(ValueError, match="Corrupted or unsupported"):
        package_builder.convert_to_canonical_wav(corrupted_file, tmp_path / "out2.wav")


def test_mixed_mp3_wav_and_silent_package_assembly(tmp_path):
    session_dir = tmp_path / "session_mixed"
    mp3_slide = create_synthetic_mp3(tmp_path / "s1.mp3", duration_ms=3000)
    wav_slide = create_synthetic_wav(tmp_path / "s3.wav", duration_ms=4000)

    slide_audios = {
        1: mp3_slide,
        2: None,  # SILENT
        3: wav_slide
    }
    slide_notes = {1: "MP3 Note", 2: "Silent Note", 3: "WAV Note"}
    slide_types = {1: "AUDIO", 2: "SILENT", 3: "AUDIO"}

    manifest_path = package_builder.build_hr_package(
        session_id="mixed_sess",
        session_dir=session_dir,
        presentation_filename="deck.pptx",
        slide_count=3,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types
    )
    assert manifest_path.exists()

    timeline_p = session_dir / "presentation_timeline.json"
    with open(timeline_p, "r", encoding="utf-8") as f:
        tl = json.load(f)

    # 3000ms + 5000ms + 4000ms = ~12000ms
    assert abs(tl["duration_ms"] - 12000) < 100
    assert len(tl["events"]) == 3

    narration_p = session_dir / "narration.wav"
    assert narration_p.exists()
    dur_ms = package_builder.get_wav_duration_ms(narration_p)
    assert abs(dur_ms - 12000) < 100


def test_grouped_mp3_narration_single_concatenation(tmp_path):
    session_dir = tmp_path / "session_grp_mp3"
    grp_mp3 = create_synthetic_mp3(tmp_path / "group.mp3", duration_ms=6000)

    slide_audios = {1: grp_mp3, 2: None}
    slide_notes = {1: "Group Master", 2: "Group Linked"}
    slide_types = {1: "GROUP_MASTER", 2: "GROUP_LINKED"}
    slide_groups = {
        1: {"group_id": "g12", "group_slides": [1, 2], "duration_ms": 6000},
        2: {"group_id": "g12", "master_slide": 1}
    }

    manifest_path = package_builder.build_hr_package(
        session_id="grp_mp3_sess",
        session_dir=session_dir,
        presentation_filename="deck.pptx",
        slide_count=2,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types,
        slide_groups=slide_groups
    )
    assert manifest_path.exists()

    with open(session_dir / "presentation_timeline.json", "r", encoding="utf-8") as f:
        tl = json.load(f)

    assert abs(tl["duration_ms"] - 6000) < 100
    events = tl["events"]
    assert len(events) == 2
    assert events[0]["slide"] == 1
    assert events[1]["slide"] == 2
    assert abs(events[1]["time_ms"] - 3000) < 50
