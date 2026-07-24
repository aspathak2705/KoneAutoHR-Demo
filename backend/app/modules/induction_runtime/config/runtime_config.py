from pydantic import BaseModel

class RuntimeConfig(BaseModel):
    voice_enabled: bool = True
    auto_advance: bool = True
    allow_questions: bool = True
    speech_rate: float = 1.0
    simulation_mode: bool = True
