import sys
import asyncio
if sys.platform == "win32":
    # Playwright requires ProactorEventLoop on Windows to handle subprocess pipes
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

print("=" * 60)
print("MAIN.PY IMPORTED")
print(sys.executable)
print(asyncio.get_event_loop_policy())
print("=" * 60)

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.dependencies import verify_token
from app.core.logging import setup_logging
from app.api.v1 import health, session, upload, presentation, employee_list, presentation_script, presentation_questions
from app.modules.induction.router import router as induction_router
from app.core.middleware import (
    RequestIDMiddleware,
    ProcessTimeMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from app.core.config import validate_llm_settings
    validate_llm_settings()

    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Self-healing database initialization (creates tables if starting from scratch)
    from app.db.database import engine, Base
    # Import all models to register on metadata
    from app.models.session import Session
    from app.models.upload import Upload
    from app.models.meeting import Meeting
    from app.models.runtime import Runtime
    from app.models.runtime_message import RuntimeMessage
    from app.models.presentation import Presentation
    from app.models.presentation_metadata import PresentationMetadata
    from app.models.presentation_script import PresentationScript
    from app.models.presentation_question import PresentationQuestion
    from app.models.presentation_job import PresentationJob
    from app.models.employee_list import EmployeeList
    from app.models.organization_config import OrganizationConfig

    # Database tables established purely via migrations. metadata.create_all deleted.

    try:
        from alembic.config import Config
        from alembic import command
        # Run Alembic migrations programmatically
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database Initialization | Alembic migrations applied successfully.")
    except Exception as e:
        logger.error(f"Database Initialization | Alembic migration error: {e}")

    from app.db.database import SessionLocal
    from app.services.runtime_scheduler_service import runtime_scheduler_service

    try:
        with SessionLocal() as db:
            runtime_scheduler_service.startup_recovery(db)
    except Exception as e:
        logger.error(f"StartupRecovery | Error: {e}")

    async def _scheduler_background_loop():
        while True:
            try:
                with SessionLocal() as db:
                    runtime_scheduler_service.poll_scheduled_launches(db)
            except Exception as e:
                logger.error(f"SchedulerWorker | Error: {e}")
            await asyncio.sleep(5)

    scheduler_task = asyncio.create_task(_scheduler_background_loop())
    try:
        yield
    finally:
        scheduler_task.cancel()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ProcessTimeMiddleware)
app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With", "X-AutoHR-Token"],
)

register_exception_handlers(app)

from app.modules.configuration.configuration_router import router as configuration_router
from app.modules.analytics.analytics_router import router as analytics_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.runtime import router as runtime_router
from app.api.v1 import assets
from app.api.v1.meeting_bot import router as meeting_bot_router
from app.api.v1.semantic_browser import router as semantic_browser_router
from app.api.v1.presentation_observer import router as presentation_observer_router

app.include_router(health.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(upload.router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(induction_router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(presentation.router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(employee_list.router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(presentation_script.router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(presentation_questions.router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(configuration_router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(analytics_router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(meetings_router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(runtime_router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(assets.router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(meeting_bot_router, prefix="/api/v1", dependencies=[Depends(verify_token)])
app.include_router(semantic_browser_router, prefix="/api/v1/semantic-browser", dependencies=[Depends(verify_token)])
app.include_router(presentation_observer_router, prefix="/api/v1/presentation-observer", dependencies=[Depends(verify_token)])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
