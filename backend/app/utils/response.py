from typing import Any, Optional
from pydantic import BaseModel

class StandardResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None

def success_response(data: Any = None, message: Optional[str] = None) -> dict:
    return {"success": True, "message": message, "data": data}

def error_response(message: str, data: Any = None) -> dict:
    return {"success": False, "message": message, "data": data}
