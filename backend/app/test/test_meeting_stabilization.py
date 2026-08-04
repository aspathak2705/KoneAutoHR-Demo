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
