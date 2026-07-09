from loguru import logger

class NemotronTTSStub:
    def __init__(self):
        logger.info("Initializing Nemotron TTS Interface (Stub)")

    async def text_to_speech(self, text: str, voice_id: str = "default") -> bytes:
        """
        Stub for streaming TTS from Nemotron Speech.
        Returns dummy audio bytes.
        """
        logger.info(f"TTS Stub: Speaking text '{text[:40]}...' using voice {voice_id}")
        return b"DUMMY_AUDIO_BYTES_FROM_NEMOTRON_TTS"

tts_interface = NemotronTTSStub()
