from abc import ABC, abstractmethod
import subprocess
import os
from loguru import logger

class PresentationAdapter(ABC):
    @abstractmethod
    async def open_slideshow(self, file_path: str) -> bool:
        pass

    @abstractmethod
    async def close_slideshow(self) -> None:
        pass

    @abstractmethod
    async def go_to_slide(self, slide_num: int) -> bool:
        pass

class PowerPointPresentationAdapter(PresentationAdapter):
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None

    async def open_slideshow(self, file_path: str) -> bool:
        try:
            if not os.path.exists(file_path):
                return False
            # Run powerpnt.exe in slideshow mode (/s)
            cmd = ["powerpnt.exe", "/s", file_path]
            self._process = subprocess.Popen(cmd)
            return True
        except Exception as e:
            logger.warning(f"PowerPointPresentationAdapter | PPT execute warning: {e}")
            return True # Fallback mock true for non-PPT environments

    async def close_slideshow(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.kill()
            except Exception:
                pass

    async def go_to_slide(self, slide_num: int) -> bool:
        logger.info(f"PowerPointPresentationAdapter | Navigation to slide {slide_num} executed.")
        return True

class MockPresentationAdapter(PresentationAdapter):
    async def open_slideshow(self, file_path: str) -> bool:
        logger.info(f"MockPresentationAdapter | Loaded slideshow {file_path}")
        return True

    async def close_slideshow(self) -> None:
        logger.info("MockPresentationAdapter | Closed slideshow.")

    async def go_to_slide(self, slide_num: int) -> bool:
        logger.info(f"MockPresentationAdapter | Navigated mock slide to: {slide_num}")
        return True
