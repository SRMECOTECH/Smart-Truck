"""
Standalone script to refresh all summary tables in MySQL.
Run after data migration or on a schedule (e.g., cron every 15 min).

Usage: python scripts/refresh_summaries.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymysql
from pymysql.cursors import DictCursor
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "smart_truck",
    "charset": "utf8mb4",
}


def refresh(conn):
    from migrations.migrate_data import refresh_summaries
    refresh_summaries(conn)


def main():
    logger.info("Refreshing all summary tables...")
    conn = pymysql.connect(**DB_CONFIG, cursorclass=DictCursor)
    try:
        refresh(conn)
        logger.info("All summaries refreshed!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
