from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.database import engine
from app.db.base import Base
from app.api.v1 import health, session, upload
from app.modules.induction.router import router as induction_router
from app.core.middleware import (
    RequestIDMiddleware,
    ProcessTimeMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from app.core.config import validate_llm_settings
    validate_llm_settings()
    
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

# Request Interceptor Middlewares (Starlette onion: executed bottom-up)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ProcessTimeMiddleware)
app.add_middleware(RequestIDMiddleware)

# Global Exceptions Mapper
register_exception_handlers(app)

# Include v1 versioned routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(induction_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
