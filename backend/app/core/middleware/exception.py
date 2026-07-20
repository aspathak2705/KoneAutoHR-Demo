from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from app.core.exceptions import (
    SessionNotFoundException,
    InvalidUploadException,
    StorageException,
    ValidationException
)

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(SessionNotFoundException)
    async def session_not_found_handler(request: Request, exc: SessionNotFoundException):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": str(exc), "request_id": request_id}
        )

    @app.exception_handler(InvalidUploadException)
    async def invalid_upload_handler(request: Request, exc: InvalidUploadException):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(exc), "request_id": request_id}
        )

    @app.exception_handler(ValidationException)
    async def validation_handler(request: Request, exc: ValidationException):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(exc), "request_id": request_id}
        )

    @app.exception_handler(StorageException)
    async def storage_handler(request: Request, exc: StorageException):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"StorageException: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Storage system error occurred.", "request_id": request_id}
        )

    from app.core.exceptions import InvalidResponseError, LLMResponseParseError, LLMResponseValidationError

    @app.exception_handler(InvalidResponseError)
    @app.exception_handler(LLMResponseParseError)
    @app.exception_handler(LLMResponseValidationError)
    async def invalid_response_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"InvalidResponseError caught on request {request_id}: {str(exc)}")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "The AI returned an invalid response format. Please try again.",
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
                "message": "Internal Server Error",
                "request_id": request_id,
                "detail": str(exc)
            }
        )
