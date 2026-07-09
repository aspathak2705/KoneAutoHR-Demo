import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from loguru import logger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.database import engine
from app.db.base import Base
from app.api.v1 import health, session, upload

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    Base.metadata.create_all(bind=engine)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP Request Diagnostics Middleware
@app.middleware("http")
async def diagnostics_middleware(request: Request, call_next):
    # 1. Request ID Generation / Propagation
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    # 2. Timing
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        # Fallback logging if exception bypasses default handlers
        logger.exception(f"Request {request_id} crashed during execution: {request.method} {request.url.path}")
        raise exc

    process_time = time.perf_counter() - start_time
    formatted_time = f"{process_time:.4f}s"

    # 3. Response Headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = formatted_time

    # 4. Logger Info
    client_host = request.client.host if request.client else "unknown"
    logger.info(
        f"[{request_id}] {client_host} -> {request.method} {request.url.path} | "
        f"Status: {response.status_code} | Time: {formatted_time}"
    )

    return response

# Global Unhandled Exception Handler
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

# Include v1 versioned routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
