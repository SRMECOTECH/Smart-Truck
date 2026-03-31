"""
Centralized logging configuration for all Smart-Truck services.
Call setup_logging() once at application startup.
"""

import logging
import sys

from config.settings import settings


def setup_logging(service_name: str = "smart-truck", level: str | None = None):
    """Configure root logger with consistent format across all services.

    Args:
        service_name: Identifies the service in log output (e.g. 'backend', 'ml-service').
        level: Override log level (default: from .env LOG_LEVEL).
    """
    log_level = getattr(logging, (level or settings.LOG_LEVEL).upper(), logging.INFO)

    # Build format with service name
    fmt = f"%(asctime)s [{service_name}] [%(levelname)s] %(name)s: %(message)s"

    # Remove existing handlers to avoid duplicates on reload
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root.setLevel(log_level)
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pymysql").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging initialized: service=%s level=%s db=%s:%s/%s",
        service_name, logging.getLevelName(log_level),
        settings.DB_HOST, settings.DB_PORT, settings.DB_NAME,
    )
    return logger
