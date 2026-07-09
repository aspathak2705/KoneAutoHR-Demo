class DomainException(Exception):
    """Base exception class for all domain errors."""
    pass

class SessionNotFoundException(DomainException):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session with ID {session_id} not found.")

class InvalidUploadException(DomainException):
    """Raised when an uploaded file fails format or mime validation."""
    pass

class StorageException(DomainException):
    """Raised when file storage operations fail."""
    pass

class ValidationException(DomainException):
    """Generic business validation exception."""
    pass
