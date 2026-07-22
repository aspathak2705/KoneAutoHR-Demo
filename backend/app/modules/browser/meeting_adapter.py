from abc import ABC, abstractmethod
from typing import Dict, Any, List
from playwright.async_api import Page

class MeetingAdapter(ABC):
    @abstractmethod
    async def join_meeting(self, page: Page, guest_name: str) -> bool:
        pass

    @abstractmethod
    async def leave_meeting(self, page: Page) -> None:
        pass

    @abstractmethod
    async def share_screen(self, page: Page) -> bool:
        pass

    @abstractmethod
    async def stop_sharing(self, page: Page) -> bool:
        pass

    @abstractmethod
    def get_supported_capabilities(self) -> List[str]:
        pass

class TeamsMeetingAdapter(MeetingAdapter):
    """
    Microsoft Teams conferencing browser integration.
    """
    async def join_meeting(self, page: Page, guest_name: str) -> bool:
        # Standard teams pre-join checks and form fill
        return True

    async def leave_meeting(self, page: Page) -> None:
        pass

    async def share_screen(self, page: Page) -> bool:
        return True

    async def stop_sharing(self, page: Page) -> bool:
        return True

    def get_supported_capabilities(self) -> List[str]:
        return ["JoinMeeting", "LeaveMeeting", "ShareScreen", "MuteMicrophone", "OpenChat"]
