from loguru import logger

class ParakeetASRStub:
    def __init__(self):
        logger.info("Initializing Parakeet ASR Interface (Stub)")

    async def speech_to_text(self, audio_data: bytes) -> str:
        """
        Stub for Parakeet ASR transcription.
        Returns dummy text.
        """
        logger.info(f"ASR Stub: Transcribing {len(audio_data)} bytes of audio data")
        return "This is a transcribed message from the employee."

asr_interface = ParakeetASRStub()
