from loguru import logger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import json
import time
from app.core.config import settings

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = getattr(request.state, "request_id", "unknown")
        client_host = request.client.host if request.client else "unknown"
        
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        
        # Dynamically extract runtime context IDs from headers, query params or path segments
        session_id = request.query_params.get("session_id") or request.headers.get("X-Session-ID")
        employee_id = request.query_params.get("employee_id") or request.headers.get("X-Employee-ID")
        runtime_id = request.query_params.get("runtime_id") or request.headers.get("X-Runtime-ID")
        job_id = request.query_params.get("job_id") or request.headers.get("X-Job-ID")
        presentation_id = request.query_params.get("presentation_id") or request.headers.get("X-Presentation-ID")

        # Parse route path segments for context fallback
        path_parts = request.url.path.strip("/").split("/")
        if len(path_parts) > 2:
            if "session" in path_parts:
                idx = path_parts.index("session")
                if idx + 1 < len(path_parts):
                    session_id = session_id or path_parts[idx + 1]
            if "runtime" in path_parts:
                idx = path_parts.index("runtime")
                if idx + 1 < len(path_parts):
                    runtime_id = runtime_id or path_parts[idx + 1]
            if "presentation" in path_parts:
                idx = path_parts.index("presentation")
                if idx + 1 < len(path_parts):
                    presentation_id = presentation_id or path_parts[idx + 1]

        # Inject correlation metrics
        log_payload = {
            "request_id": request_id,
            "client_host": client_host,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_seconds": round(process_time, 4),
            "context": {
                "session_id": session_id,
                "employee_id": employee_id,
                "runtime_id": runtime_id,
                "job_id": job_id,
                "presentation_id": presentation_id
            }
        }

        if settings.LOG_FORMAT.lower() == "json":
            # Output structured JSON
            logger.info(json.dumps(log_payload))
        else:
            # Human-readable format with runtime context details
            context_str = ", ".join(f"{k}={v}" for k, v in log_payload["context"].items() if v)
            context_suffix = f" | Context: {{{context_str}}}" if context_str else ""
            logger.info(
                f"[{request_id}] {client_host} -> {request.method} {request.url.path} | "
                f"Status: {response.status_code} | Duration: {round(process_time, 4)}s{context_suffix}"
            )

        return response
