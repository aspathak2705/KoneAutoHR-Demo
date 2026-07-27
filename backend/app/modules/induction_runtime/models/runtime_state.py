from enum import Enum

class RuntimeState(str, Enum):
    """
    LOCKED State Machine - Do not invent new states.
    
    These 13 states represent the complete runtime lifecycle and must not be modified.
    Each state has a single responsibility and transitions happen in strict order.
    """
    # Initial state - runtime object created but not prepared
    NOT_CREATED = "NOT_CREATED"
    
    # Preparation phase - assets verified, configuration loaded
    PREPARING = "PREPARING"
    
    # Ready for induction - assets loaded, can start induction
    READY = "READY"
    
    # Induction starting - initializing components
    STARTING = "STARTING"
    
    # Browser launched and ready
    BROWSER_READY = "BROWSER_READY"
    
    # Joining Teams meeting
    JOINING = "JOINING"
    
    # Waiting in waiting room
    WAITING = "WAITING"
    
    # Connected to meeting and ready to present
    CONNECTED = "CONNECTED"
    
    # Currently presenting
    PRESENTING = "PRESENTING"
    
    # Presentation finished
    FINISHED = "FINISHED"
    
    # Runtime shutting down
    STOPPING = "STOPPING"
    
    # Runtime stopped successfully
    STOPPED = "STOPPED"
    
    # Runtime encountered an error
    FAILED = "FAILED"
    
    # Backward compatibility aliases for verification script
    CREATED = "NOT_CREATED"
    WAITING_FOR_PRESENTATION = "WAITING"
    INTRODUCTION = "CONNECTED"
    QUESTION_ANSWER = "PRESENTING"
    COMPLETED = "FINISHED"
