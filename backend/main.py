import sys
import asyncio
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

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
    
    # Non-destructive SQLite Database Auto-Migration (Preserves all user data across restarts)
    db_file = Path("autohr.db")
    import sqlite3
    from loguru import logger
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        def add_column_if_missing(table, col, col_type):
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [row[1] for row in cursor.fetchall()]
            if cols and col not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                logger.info(f"Database Auto-Migration | Added missing column '{col}' to table '{table}'.")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runtimes'")
        if cursor.fetchone():
            add_column_if_missing("runtimes", "current_step", "VARCHAR DEFAULT 'IDLE'")
            add_column_if_missing("runtimes", "meeting_status", "VARCHAR DEFAULT 'DISCONNECTED'")
            add_column_if_missing("runtimes", "started_at", "DATETIME")
            add_column_if_missing("runtimes", "connected_at", "DATETIME")
            add_column_if_missing("runtimes", "completed_at", "DATETIME")
            add_column_if_missing("runtimes", "last_error", "VARCHAR")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        if cursor.fetchone():
            add_column_if_missing("sessions", "presentation_id", "VARCHAR")
            add_column_if_missing("sessions", "employee_list_id", "VARCHAR")

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Database Auto-Migration notice: {e}")

    Base.metadata.create_all(bind=engine)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Execute startup recovery ONCE on server startup
    import asyncio
    from app.db.database import SessionLocal
    from app.services.runtime_scheduler_service import runtime_scheduler_service

    try:
        with SessionLocal() as db:
            runtime_scheduler_service.startup_recovery(db)
    except Exception as e:
        logger.error(f"StartupRecovery | Error: {e}")

    # Spawn background scheduler worker loop to poll scheduled launches every 5 seconds
    async def _scheduler_background_loop():
        while True:
            try:
                with SessionLocal() as db:
                    runtime_scheduler_service.poll_scheduled_launches(db)
            except Exception as e:
                logger.error(f"SchedulerWorker | Error: {e}")
            await asyncio.sleep(5)

    scheduler_task = asyncio.create_task(_scheduler_background_loop())
    yield
    scheduler_task.cancel()

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

from app.modules.configuration.configuration_router import router as configuration_router
from app.modules.analytics.analytics_router import router as analytics_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.runtime import router as runtime_router

from app.api.v1 import assets
from app.api.v1 import presentation_runtime

# Include v1 versioned routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(induction_router, prefix="/api/v1")
app.include_router(presentation.router, prefix="/api/v1")
app.include_router(employee_list.router, prefix="/api/v1")
app.include_router(presentation_script.router, prefix="/api/v1")
app.include_router(presentation_questions.router, prefix="/api/v1")
app.include_router(configuration_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(meetings_router, prefix="/api/v1")
app.include_router(runtime_router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(presentation_runtime.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
