class BaseAppException(Exception):
    """Base exception class for all application errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class ValidationException(BaseAppException):
    """Raised when request payloads, file uploads, or validation parameters fail logic constraints."""
    pass

class RuntimeException(BaseAppException):
    """Raised during presentation runtime execution or state loops failures."""
    pass

class StorageException(BaseAppException):
    """Raised when file storage or asset operations fail."""
    pass

class BrowserException(BaseAppException):
    """Raised when Teams browser driver or page interactions fail."""
    pass

class LLMException(BaseAppException):
    """Base LLM connection or response validation failure exceptions."""
    pass

# Domain mapping back-compat subclass layers
class SessionNotFoundException(ValidationException):
    def __init__(self, session_id: str):
        super().__init__(f"Session with ID {session_id} not found.", {"session_id": session_id})

class InvalidUploadException(ValidationException):
    pass

class LLMConnectionError(LLMException):
    pass

class LLMResponseParseError(LLMException):
    pass

class LLMResponseValidationError(LLMException):
    pass

class PromptRenderError(LLMException):
    pass

class InvalidResponseError(LLMException):
    pass
