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
            
            # Check sessions table
            cursor.execute("PRAGMA table_info(sessions)")
            session_cols = [row[1] for row in cursor.fetchall()]
            
            # Check presentation_scripts table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='presentation_scripts'")
            has_scripts_table = cursor.fetchone()
            script_cols = []
            if has_scripts_table:
                cursor.execute("PRAGMA table_info(presentation_scripts)")
                script_cols = [row[1] for row in cursor.fetchall()]
                
            # Check organization_config table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organization_config'")
            has_config_table = cursor.fetchone()
            
            # Check invitation_drafts table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invitation_drafts'")
            has_drafts_table = cursor.fetchone()
            
            # Check meetings table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meetings'")
            has_meetings_table = cursor.fetchone()

            # Check runtimes table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runtimes'")
            has_runtimes_table = cursor.fetchone()

            # Check runtime_messages table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runtime_messages'")
            has_messages_table = cursor.fetchone()
            
            conn.close()
            
            needs_reset = False
            if session_cols and "presentation_id" not in session_cols:
                needs_reset = True
            if script_cols and "status" not in script_cols:
                needs_reset = True
            if not has_config_table or not has_drafts_table or not has_meetings_table or not has_runtimes_table or not has_messages_table:
                needs_reset = True
                
            if needs_reset:
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

from app.modules.configuration.configuration_router import router as configuration_router
from app.modules.analytics.analytics_router import router as analytics_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.runtime import router as runtime_router

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
