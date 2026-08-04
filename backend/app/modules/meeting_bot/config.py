import os

class MeetingBotConfig:
    def __init__(self):
        self.headless: bool = os.environ.get("BOT_BROWSER_HEADLESS", "false").lower() == "true"
        self.slow_mo: int = int(os.environ.get("BOT_BROWSER_SLOW_MO", "50"))
        self.viewport_width: int = int(os.environ.get("BOT_BROWSER_WIDTH", "1280"))
        self.viewport_height: int = int(os.environ.get("BOT_BROWSER_HEIGHT", "720"))
        self.use_fake_devices: bool = os.environ.get("BOT_USE_FAKE_DEVICES", "false").lower() == "true"
        self.audio_route: str = os.environ.get("BOT_AUDIO_ROUTE", "teams-microphone").strip() or "teams-microphone"
        self.audio_input_device_name: str = os.environ.get("BOT_AUDIO_INPUT_DEVICE_NAME", "").strip()
        self.audio_output_device_name: str = os.environ.get("BOT_AUDIO_OUTPUT_DEVICE_NAME", "").strip()
        
        # Connection timeouts and retries
        self.timeout_ms: int = int(os.environ.get("BOT_TIMEOUT_MS", "30000"))
        self.retry_count: int = int(os.environ.get("BOT_RETRY_COUNT", "3"))

        # Lobby waiting configurations
        self.lobby_wait_enabled: bool = os.environ.get("BOT_LOBBY_WAIT_ENABLED", "true").lower() == "true"
        
        # Max timeout in seconds. Default is None (infinite wait).
        timeout_env = os.environ.get("BOT_MAX_LOBBY_TIMEOUT", "None")
        if timeout_env.lower() in ("none", "null", ""):
            self.max_lobby_timeout = None
        else:
            self.max_lobby_timeout = int(timeout_env)
            
        self.polling_interval: int = int(os.environ.get("BOT_POLLING_INTERVAL", "1"))

meeting_bot_config = MeetingBotConfig()
