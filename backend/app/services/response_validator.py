from typing import Dict, Any
from app.services.session_serializer import session_serializer

class ResponseValidator:
    """
    Phase 6 — Session Validator
    Validates the generated/updated script payload structure.
    Ensures 'opening', 'slides', and 'closing' fields exist and are fully populated.
    If anything is missing, generates fallback defaults.
    """
    def validate_and_patch(self, script_content: Dict[str, Any]) -> Dict[str, Any]:
        # Delegate to session_serializer to perform schema formatting and patch default values if missing
        return session_serializer.serialize(script_content)

response_validator = ResponseValidator()
