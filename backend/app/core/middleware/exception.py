from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from app.core.exceptions import (
    BaseAppException,
    ValidationException,
    RuntimeException,
    StorageException,
    BrowserException,
    LLMException
)

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(BaseAppException)
    async def base_app_exception_handler(request: Request, exc: BaseAppException):
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Determine status code
        status_code = 500
        code = exc.__class__.__name__
        
        if isinstance(exc, ValidationException):
            status_code = 400
        elif isinstance(exc, RuntimeException):
            status_code = 500
        elif isinstance(exc, StorageException):
            status_code = 500
        elif isinstance(exc, BrowserException):
            status_code = 500
        elif isinstance(exc, LLMException):
            status_code = 502

        logger.error(f"[{request_id}] Exception: {code} - {exc.message} (details: {exc.details})")

        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "code": code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(f"Unhandled exception caught on request {request_id}: {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": {"error": str(exc)},
                "request_id": request_id
            }
        )
