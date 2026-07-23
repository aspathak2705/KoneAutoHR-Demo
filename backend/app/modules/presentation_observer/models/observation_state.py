from enum import Enum

class ObservationState(str, Enum):
    WAITING = "WAITING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    LOST = "LOST"
    ENDED = "ENDED"
