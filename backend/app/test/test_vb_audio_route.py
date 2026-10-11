import pytest
from unittest.mock import MagicMock
from app.modules.meeting_bot.media.audio_controller import AudioController


def make_devices_and_apis(device_tuples):
    """
    Helper to create mock devices list and hostapis list.
    device_tuples: list of (name, hostapi_name, max_output_channels, default_samplerate)
    """
    apis_map = {}
    apis_list = []
    for _, api_name, _, _ in device_tuples:
        if api_name not in apis_map:
            apis_map[api_name] = len(apis_list)
            apis_list.append({"name": api_name})

    devices_list = []
    for name, api_name, out_ch, sr in device_tuples:
        devices_list.append({
            "name": name,
            "hostapi": apis_map[api_name],
            "max_output_channels": out_ch,
            "max_input_channels": 0,
            "default_samplerate": sr,
        })
    return devices_list, apis_list


def test_exact_cable_input_name(monkeypatch):
    devices, apis = make_devices_and_apis([
        ("Speaker (Realtek Audio)", "MME", 2, 44100),
        ("CABLE Input (VB-Audio Virtual Cable)", "Windows DirectSound", 2, 44100),
    ])

    monkeypatch.setattr("sounddevice.query_devices", lambda: devices)
    monkeypatch.setattr("sounddevice.query_hostapis", lambda: apis)
    monkeypatch.setattr("sounddevice.check_output_settings", lambda **kw: None)

    ctrl = AudioController("test-session")
    res = ctrl.validate_audio_route()

    assert res is True
    assert ctrl._cached_device_idx == 1
    assert "CABLE Input" in ctrl._cached_device_name


def test_cable_in_16_ch_variant_name(monkeypatch):
    devices, apis = make_devices_and_apis([
        ("Speaker (Realtek Audio)", "MME", 2, 44100),
        ("CABLE In 16 Ch (2- VB-Audio Virtual Cable)", "Windows DirectSound", 16, 44100),
    ])

    monkeypatch.setattr("sounddevice.query_devices", lambda: devices)
    monkeypatch.setattr("sounddevice.query_hostapis", lambda: apis)
    monkeypatch.setattr("sounddevice.check_output_settings", lambda **kw: None)

    ctrl = AudioController("test-session")
    res = ctrl.validate_audio_route()

    assert res is True
    assert ctrl._cached_device_idx == 1
    assert "CABLE In 16 Ch" in ctrl._cached_device_name


def test_duplicate_endpoints_preferred_host_api(monkeypatch):
    devices, apis = make_devices_and_apis([
        ("CABLE In 16 Ch (2- VB-Audio Virtual Cable)", "MME", 16, 44100),
        ("CABLE In 16 Ch (2- VB-Audio Virtual Cable)", "Windows DirectSound", 16, 44100),
        ("CABLE In 16 Ch (2- VB-Audio Virtual Cable)", "Windows WASAPI", 2, 48000),
    ])

    monkeypatch.setattr("sounddevice.query_devices", lambda: devices)
    monkeypatch.setattr("sounddevice.query_hostapis", lambda: apis)
    monkeypatch.setattr("sounddevice.check_output_settings", lambda **kw: None)

    ctrl = AudioController("test-session")
    res = ctrl.validate_audio_route()

    assert res is True
    # Windows DirectSound (index 1) prioritized over MME (0) and WASAPI (2)
    assert ctrl._cached_device_idx == 1
    assert ctrl._cached_host_api == "Windows DirectSound"


def test_rejection_of_unrelated_vb_audio_devices(monkeypatch):
    devices, apis = make_devices_and_apis([
        ("Speakers (2- VB-Audio Virtual Cable)", "Windows DirectSound", 16, 44100),
        ("Output (VB-Audio Point)", "Windows WDM-KS", 16, 44100),
        ("CABLE Output (VB-Audio Virtual Cable)", "Windows DirectSound", 16, 44100),
    ])

    monkeypatch.setattr("sounddevice.query_devices", lambda: devices)
    monkeypatch.setattr("sounddevice.query_hostapis", lambda: apis)
    monkeypatch.setattr("sounddevice.check_output_settings", lambda **kw: None)

    ctrl = AudioController("test-session")
    with pytest.raises(RuntimeError, match="VB-CABLE playback device not found"):
        ctrl.validate_audio_route()


def test_missing_target_endpoint_lists_discovered_devices(monkeypatch):
    devices, apis = make_devices_and_apis([
        ("Speaker (Realtek Audio)", "MME", 2, 44100),
        ("Headphones (Realtek Audio)", "Windows DirectSound", 2, 48000),
    ])

    monkeypatch.setattr("sounddevice.query_devices", lambda: devices)
    monkeypatch.setattr("sounddevice.query_hostapis", lambda: apis)
    monkeypatch.setattr("sounddevice.check_output_settings", lambda **kw: None)

    ctrl = AudioController("test-session")
    with pytest.raises(RuntimeError) as exc_info:
        ctrl.validate_audio_route()

    err = str(exc_info.value)
    assert "VB-CABLE playback device not found" in err
    assert "Speaker (Realtek Audio)" in err
    assert "Headphones (Realtek Audio)" in err


def test_incompatible_format_or_sample_rate_rejected(monkeypatch):
    devices, apis = make_devices_and_apis([
        ("CABLE Input", "Windows WASAPI", 2, 48000),
    ])

    monkeypatch.setattr("sounddevice.query_devices", lambda: devices)
    monkeypatch.setattr("sounddevice.query_hostapis", lambda: apis)
    
    # Always raise format check error
    def fail_check(**kw):
        raise ValueError("Invalid sample rate or channels")

    monkeypatch.setattr("sounddevice.check_output_settings", fail_check)

    ctrl = AudioController("test-session")
    with pytest.raises(RuntimeError, match="VB-CABLE playback candidate validation failed"):
        ctrl.validate_audio_route()
