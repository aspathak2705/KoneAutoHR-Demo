import base64
import requests
import io
import wave
import asyncio
from loguru import logger

class ConfigurationError(Exception):
    pass

class SarvamClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.url = "https://api.sarvam.ai/text-to-speech"

    async def text_to_speech(self, text: str, voice: str = "aayan") -> bytes:
        """
        Synthesize text into WAV bytes using Sarvam TTS API.
        Raises ConfigurationError if the API key is not set.
        """
        if not self.api_key:
            raise ConfigurationError("VOICE_PROVIDER_NOT_CONFIGURED")

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [text],
            "speaker": voice,
            "pace": 0.92,
            "speech_rate": 0.88,
            "model": "bulbul:v3",
            "target_aud_format": "wav"
        }

        def post_request():
            return requests.post(self.url, json=payload, headers=headers, timeout=60)

        response = await asyncio.to_thread(post_request)
        if response.status_code != 200:
            raise RuntimeError(f"Sarvam TTS API failed with status {response.status_code}: {response.text}")

        data = response.json()
        audios = data.get("audios", [])
        if not audios:
            raise RuntimeError("Sarvam TTS API response did not contain audio data.")

        return base64.b64decode(audios[0])

    @staticmethod
    def get_audio_duration(audio_bytes: bytes) -> float:
        """
        Extract exact duration of WAV audio bytes in seconds.
        """
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate > 0:
                    return float(frames) / rate
        except Exception as e:
            logger.error(f"SarvamClient | Failed to parse WAV duration: {e}")
        return 0.0
