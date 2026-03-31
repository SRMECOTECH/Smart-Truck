"""
Centralized database connections for all Smart-Truck services.
Provides: get_connection, get_db (FastAPI), db_session (scripts), get_conn (simple).
"""

import logging
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager

from config.settings import settings

logger = logging.getLogger(__name__)


def get_connection(**overrides):
    """Create a new MySQL connection using centralized config.

    Args:
        **overrides: Any pymysql.connect kwargs to override (e.g. local_infile=True).
    """
    cfg = {**settings.DB_CONFIG, "cursorclass": DictCursor, "autocommit": False}
    cfg.update(overrides)
    logger.debug(
        "Opening DB connection to %s:%s/%s",
        cfg["host"], cfg["port"], cfg["database"],
    )
    return pymysql.connect(**cfg)


def get_conn(**overrides):
    """Simple alias — returns a connection (useful for ML service/scripts)."""
    return get_connection(**overrides)


def get_db():
    """FastAPI dependency: yields a DB connection, auto-closes after request."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def db_session(**overrides):
    """Context manager for scripts/services outside FastAPI."""
    conn = get_connection(**overrides)
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Create the smart_truck database if it doesn't exist."""
    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {settings.DB_NAME}")
        conn.commit()
        logger.info("Database '%s' ensured.", settings.DB_NAME)
    finally:
        conn.close()
