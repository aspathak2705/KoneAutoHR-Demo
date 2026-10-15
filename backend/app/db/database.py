from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from loguru import logger
from app.core.config import settings

DATABASE_URL = settings.AUTOHR_DATABASE_URL

# Driver and connection arguments
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif "postgres" in DATABASE_URL:
    # Disable prepared statement caching for Supabase transaction pooler (pgbouncer port 6543)
    connect_args["prepare_threshold"] = None
    # TCP keepalives to prevent AWS/Supabase ELB dropping idle connections
    connect_args["keepalives"] = 1
    connect_args["keepalives_idle"] = 30
    connect_args["keepalives_interval"] = 10
    connect_args["keepalives_count"] = 5

engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args, 
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_database_connectivity() -> dict:
    """
    Safe connectivity check:
    Reports target host/database in sanitized form without logging credentials.
    """
    target = settings.DATABASE_TARGET_INFO
    result = {
        "status": "disconnected",
        "target": target,
        "sanitized_url": settings.SANITIZED_DATABASE_URL,
        "error": None
    }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["status"] = "connected"
    except Exception as e:
        # Scrub credentials from error message if present
        err_msg = str(e)
        import re
        sanitized_err = re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", err_msg)
        result["error"] = sanitized_err
        logger.warning(f"Database connectivity check failed for target {target['host']}: {sanitized_err}")

    return result

