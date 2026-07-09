from loguru import logger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = getattr(request.state, "request_id", "unknown")
        client_host = request.client.host if request.client else "unknown"

        response = await call_next(request)

        process_time = response.headers.get("X-Process-Time", "0.0s")
        logger.info(
            f"[{request_id}] {client_host} -> {request.method} {request.url.path} | "
            f"Status: {response.status_code} | Time: {process_time}"
        )
        return response
