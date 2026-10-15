import sys
import re
from loguru import logger
from app.core.config import settings

# Sensitive patterns to scrub from all logs
SENSITIVE_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE), r"\1[SCRUBBED]"),
    (re.compile(r"(X-AutoHR-Token['\":\s=]+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE), r"\1[SCRUBBED]"),
    (re.compile(r"(password['\":\s=]+)[^'\"\s,&]+", re.IGNORECASE), r"\1[SCRUBBED]"),
    (re.compile(r"(api[_-]?key['\":\s=]+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE), r"\1[SCRUBBED]"),
]

def scrub_sensitive_message(message: str) -> str:
    """Scrub tokens, credentials, and sensitive API keys from log strings."""
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message

def log_filter(record) -> bool:
    """Scrub record message in place before emitting to sinks."""
    record["message"] = scrub_sensitive_message(record["message"])
    return True

def setup_logging():
    # Remove default handler
    logger.remove()

    # Add stdout handler with scrubbing filter
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        filter=log_filter,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # Add file handler with scrubbing filter
    logger.add(
        "logs/autohr.log",
        rotation="10 MB",
        retention="1 week",
        level=settings.LOG_LEVEL,
        filter=log_filter,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    # Optional: Azure Application Insights exporter if connection string configured
    appinsights_cs = getattr(settings, "APPLICATIONINSIGHTS_CONNECTION_STRING", None)
    if appinsights_cs:
        try:
            # Check for azure-monitor-opentelemetry or opencensus-ext-azure
            from opencensus.ext.azure.log_exporter import AzureLogHandler
            import logging as py_logging
            azure_handler = AzureLogHandler(connection_string=appinsights_cs)
            logger.add(
                azure_handler,
                level="INFO",
                filter=log_filter
            )
            logger.info("Logging | Azure Application Insights log exporter initialized.")
        except ImportError:
            logger.warning(
                "Logging | APPLICATIONINSIGHTS_CONNECTION_STRING is set, but opencensus-ext-azure is not installed. "
                "Install with `pip install opencensus-ext-azure` to enable cloud telemetry."
            )
        except Exception as e:
            logger.error(f"Logging | Failed to initialize Application Insights exporter: {e}")

    logger.info("Logging initialized.")
