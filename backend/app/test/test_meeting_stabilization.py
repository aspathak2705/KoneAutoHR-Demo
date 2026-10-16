import asyncio

import pytest

from app.modules.meeting_bot.teams.teams_controller import TeamsController
from app.modules.presentation.presentation_runtime_controller import PresentationRuntimeController


def test_run_with_retries_stops_after_attempts() -> None:
    controller = TeamsController()
    attempts = []

    async def flaky_action() -> None:
        attempts.append(1)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(controller._run_with_retries(flaky_action, attempts=3, delay=0))

    assert len(attempts) == 3


def test_run_with_retries_returns_on_success() -> None:
    controller = TeamsController()

    async def success_action() -> str:
        return "ok"

    result = asyncio.run(controller._run_with_retries(success_action, attempts=3, delay=0))

    assert result == "ok"


def test_share_retry_resets_share_flow_before_restarting() -> None:
    controller = PresentationRuntimeController("session-1", "demo.pptx", teams_page=None)
    events = []

    async def fake_share(page: object) -> bool:
        events.append("share")
        if len(events) == 1:
            raise RuntimeError("share failed")
        return True

    async def fake_reset(page: object) -> None:
        events.append("reset")

    async def fake_verify(page: object) -> bool:
        events.append("verify")
        return True

    controller._reset_share_flow = fake_reset
    controller._wait_for_sharing_confirmed = fake_verify

    result = asyncio.run(controller._share_with_retry(fake_share, object()))

    assert result is True
    assert events == ["share", "reset", "share", "verify"]


def test_wait_for_prejoin_detects_light_meetings_prejoin_screen() -> None:
    controller = TeamsController()

    class FakeLocator:
        def __init__(self, visible=False, count_val=0):
            self._visible = visible
            self._count = count_val

        @property
        def first(self):
            return self

        async def is_visible(self, timeout=None):
            return self._visible

        async def count(self):
            return self._count

    class FakePage:
        def __init__(self, url):
            self.url = url
            self.context = self

        @property
        def pages(self):
            return [self]

        def is_closed(self):
            return False

        async def title(self):
            return "Join conversation"

        def locator(self, selector):
            # Match prejoin join button on light-meetings
            if "join" in selector.lower():
                return FakeLocator(visible=True, count_val=1)
            return FakeLocator(visible=False, count_val=0)

    page = FakePage("https://teams.live.com/light-meetings/launch?meeting_id=123")
    res_page = asyncio.run(controller.wait_for_prejoin(page))
    assert res_page.url == "https://teams.live.com/light-meetings/launch?meeting_id=123"

