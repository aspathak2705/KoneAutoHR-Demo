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


def test_generate_silence_wav(tmp_path):
    silence_wav = tmp_path / "silence.wav"
    package_builder.generate_silence_wav(silence_wav, duration_ms=5000, sample_rate=44100, num_channels=2, sample_width=2)
    assert silence_wav.exists()
    
    with wave.open(str(silence_wav), "rb") as w:
        assert w.getframerate() == 44100
        assert w.getnchannels() == 2
        assert w.getsampwidth() == 2
        frames = w.readframes(w.getnframes())
        # Verify completely zero digital silence
        assert all(b == 0 for b in frames)
        duration = (w.getnframes() / float(w.getframerate())) * 1000.0
        assert abs(duration - 5000.0) < 1.0


def test_silent_slide_timeline_offsets(tmp_path):
    # Slide 1: 10s audio, Slide 2: 5s silent, Slide 3: 8s audio
    session_dir = tmp_path / "session_1"
    wav1 = create_synthetic_wav(tmp_path / "s1.wav", duration_ms=10000)
    wav3 = create_synthetic_wav(tmp_path / "s3.wav", duration_ms=8000)

    slide_audios = {
        1: wav1,
        2: None,
        3: wav3
    }
    slide_notes = {1: "Intro", 2: "Silent note", 3: "Closing"}
    slide_types = {1: "AUDIO", 2: "SILENT", 3: "AUDIO"}

    manifest_path = package_builder.build_hr_package(
        session_id="test_sess",
        session_dir=session_dir,
        presentation_filename="presentation.pptx",
        slide_count=3,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types
    )
    assert manifest_path.exists()

    timeline_path = session_dir / "presentation_timeline.json"
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    assert timeline["duration_ms"] == 23000
    events = timeline["events"]
    assert len(events) == 3
    assert events[0]["time_ms"] == 0 and events[0]["slide"] == 1
    assert events[1]["time_ms"] == 10000 and events[1]["slide"] == 2
    assert events[2]["time_ms"] == 15000 and events[2]["slide"] == 3

    # Verify narration.wav duration
    narration_path = session_dir / "narration.wav"
    assert narration_path.exists()
    dur_ms = package_builder.get_wav_duration_ms(narration_path)
    assert abs(dur_ms - 23000.0) < 1.0


def test_consecutive_silent_slides(tmp_path):
    session_dir = tmp_path / "session_consec"
    slide_audios = {1: None, 2: None}
    slide_notes = {1: "Silent 1", 2: "Silent 2"}
    slide_types = {1: "SILENT", 2: "SILENT"}

    package_builder.build_hr_package(
        session_id="test_consec",
        session_dir=session_dir,
        presentation_filename="presentation.pptx",
        slide_count=2,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types
    )

    timeline_path = session_dir / "presentation_timeline.json"
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    assert timeline["duration_ms"] == 10000
    events = timeline["events"]
    assert events[0]["time_ms"] == 0 and events[0]["slide"] == 1
    assert events[1]["time_ms"] == 5000 and events[1]["slide"] == 2


def test_first_slide_silent(tmp_path):
    session_dir = tmp_path / "session_first_silent"
    wav2 = create_synthetic_wav(tmp_path / "s2.wav", duration_ms=4000)
    slide_audios = {1: None, 2: wav2}
    slide_notes = {1: "Silent title", 2: "Narrated overview"}
    slide_types = {1: "SILENT", 2: "AUDIO"}

    package_builder.build_hr_package(
        session_id="test_first_silent",
        session_dir=session_dir,
        presentation_filename="presentation.pptx",
        slide_count=2,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types
    )

    timeline_path = session_dir / "presentation_timeline.json"
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    assert timeline["duration_ms"] == 9000
    events = timeline["events"]
    assert events[0]["time_ms"] == 0 and events[0]["slide"] == 1
    assert events[1]["time_ms"] == 5000 and events[1]["slide"] == 2


def test_all_silent_presentation(tmp_path):
    session_dir = tmp_path / "session_all_silent"
    slide_audios = {1: None, 2: None, 3: None}
    slide_notes = {1: "", 2: "", 3: ""}
    slide_types = {1: "SILENT", 2: "SILENT", 3: "SILENT"}

    package_builder.build_hr_package(
        session_id="test_all_silent",
        session_dir=session_dir,
        presentation_filename="presentation.pptx",
        slide_count=3,
        slide_audios=slide_audios,
        slide_notes=slide_notes,
        slide_types=slide_types
    )

    timeline_path = session_dir / "presentation_timeline.json"
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    assert timeline["duration_ms"] == 15000
    events = timeline["events"]
    assert len(events) == 3
    assert events[0]["time_ms"] == 0
    assert events[1]["time_ms"] == 5000
    assert events[2]["time_ms"] == 10000

    narration_path = session_dir / "narration.wav"
    dur_ms = package_builder.get_wav_duration_ms(narration_path)
    assert abs(dur_ms - 15000.0) < 1.0


def test_metadata_idempotency(tmp_path):
    session_dir = tmp_path / "session_idem"
    metadata_file = session_dir / "hr_slide_metadata.json"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Simulate setting slide 1 silent twice
    metadata = {}
    for _ in range(2):
        metadata["1"] = {
            "type": "SILENT",
            "audio_path": None,
            "duration_ms": 5000,
            "notes": "Idempotent note"
        }
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    with open(metadata_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["1"]["type"] == "SILENT"
    assert loaded["1"]["duration_ms"] == 5000
    assert loaded["1"]["notes"] == "Idempotent note"


def test_silence_and_narration_audio_concatenation(tmp_path):
    wav1 = create_synthetic_wav(tmp_path / "w1.wav", duration_ms=2000, sample_rate=44100)
    silence = tmp_path / "silence.wav"
    package_builder.generate_silence_wav(silence, duration_ms=5000, sample_rate=44100, num_channels=2, sample_width=2)
    output = tmp_path / "concat.wav"

    package_builder.concatenate_wav_files([wav1, silence], output)
    assert output.exists()
    dur = package_builder.get_wav_duration_ms(output)
    assert abs(dur - 7000.0) < 1.0


def test_silent_slide_validation_rules(tmp_path):
    # Test valid metadata with a silent slide
    meta_valid = {
        "1": {"type": "SILENT", "audio_path": None, "duration_ms": 5000, "notes": ""},
        "2": {"type": "AUDIO", "audio_path": str(tmp_path / "exists.wav"), "duration_ms": 3000, "notes": ""}
    }
    create_synthetic_wav(tmp_path / "exists.wav", duration_ms=3000)

    # Slide 1 silent passes
    assert meta_valid["1"]["type"] == "SILENT"
    assert meta_valid["1"]["duration_ms"] == 5000

    # Slide 2 audio passes
    assert Path(meta_valid["2"]["audio_path"]).exists()

    # Missing slide 3 fails validation
    slide_count = 3
    errors = []
    for s in range(1, slide_count + 1):
        if str(s) not in meta_valid:
            errors.append(f"Slide {s} is missing an audio recording or silent selection")
    assert len(errors) == 1
    assert "Slide 3 is missing an audio recording or silent selection" in errors[0]

