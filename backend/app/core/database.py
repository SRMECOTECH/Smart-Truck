import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from backend.app.core.config import settings


def get_connection():
    """Create a new MySQL connection."""
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def get_db():
    """FastAPI dependency: yields a DB connection, auto-closes after request."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def db_session():
    """Context manager for scripts/services outside FastAPI."""
    conn = get_connection()
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
    finally:
        conn.close()
