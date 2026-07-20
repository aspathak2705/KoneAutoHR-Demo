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

class LLMConnectionError(DomainException):
    """Raised when the LLM provider fails to connect or returns an API error."""
    pass

class LLMResponseParseError(DomainException):
    """Raised when the LLM response cannot be parsed as JSON."""
    pass

class LLMResponseValidationError(DomainException):
    """Raised when the LLM response is missing required fields or has invalid types."""
    pass

class PromptRenderError(DomainException):
    """Raised when rendering a Jinja prompt template fails."""
    pass

class InvalidResponseError(DomainException):
    """Raised when the AI returns an invalid response format or missing required fields after retries."""
    pass
