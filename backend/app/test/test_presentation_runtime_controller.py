import pytest

from app.modules.presentation.presentation_runtime_controller import PresentationRuntimeController


class FakeTeamsController:
    def __init__(self):
        self.calls = []

    async def open_share_panel(self, page):
        self.calls.append("open_share_panel")


class FakeNativeShareController:
    def __init__(self):
        self.calls = []

    async def activate_picker(self):
        self.calls.append("activate_picker")

    async def click_window_tab(self):
        self.calls.append("click_window_tab")

    async def select_window(self, window_name: str = "PowerPoint", *, presentation_name: str | None = None):
        self.calls.append(("select_window", window_name, presentation_name))

    async def click_share(self):
        self.calls.append("click_share")


class FakeShareVerificationController:
    def __init__(self):
        self.calls = []

    async def wait_for_share_confirmation(self, page, *, timeout: float = 10.0):
        self.calls.append(("wait_for_share_confirmation", timeout))
        return True


@pytest.mark.asyncio
async def test_share_flow_uses_independent_share_controllers(monkeypatch):
    runtime = PresentationRuntimeController(session_id="session-1", ppt_path="demo.pptx", teams_page=object())
    teams_controller = FakeTeamsController()
    picker_controller = FakeNativeShareController()
    verification_controller = FakeShareVerificationController()

    monkeypatch.setattr(runtime, "_get_teams_controller", lambda: teams_controller)
    monkeypatch.setattr(runtime, "_get_native_share_controller", lambda: picker_controller)
    monkeypatch.setattr(runtime, "_get_share_verification_controller", lambda: verification_controller)

    result = await runtime._share_presentation_window(page=object())

    assert result is True
    assert teams_controller.calls == ["open_share_panel"]
    assert picker_controller.calls == [
        "activate_picker",
        "click_window_tab",
        ("select_window", "PowerPoint Slide Show", "demo.pptx"),
        "click_share",
    ]
    assert verification_controller.calls == [("wait_for_share_confirmation", 10.0)]
