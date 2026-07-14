from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.database import engine
from app.db.base import Base
from app.api.v1 import health, session, upload, presentation, employee_list, presentation_script, presentation_questions
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
    
    # Auto-reset SQLite database if schema mismatch detected
    db_file = Path("autohr.db")
    if db_file.exists():
        import sqlite3, os
        from loguru import logger
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions)")
            columns = [row[1] for row in cursor.fetchall()]
            conn.close()
            if columns and "presentation_id" not in columns:
                os.remove(db_file)
                logger.info("Schema mismatch detected: Deleted old autohr.db for clean recreation.")
        except Exception as e:
            logger.warning(f"Schema check error: {e}")

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
app.include_router(presentation.router, prefix="/api/v1")
app.include_router(employee_list.router, prefix="/api/v1")
app.include_router(presentation_script.router, prefix="/api/v1")
app.include_router(presentation_questions.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
