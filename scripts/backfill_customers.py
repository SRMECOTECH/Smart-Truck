"""
One-time script: populate customers table from CSV and backfill trips.customer_id.
Uses i_cnr_id (present in trips.cnr_id) as the link key.

Usage: python scripts/backfill_customers.py
"""

import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.database import get_conn
from config.logging_config import setup_logging

setup_logging(service_name="backfill-customers")
logger = logging.getLogger(__name__)

CSV_PATH = PROJECT_ROOT / "data-analysis" / "data" / "tbl_trip_data20260128.csv"


def main():
    logger.info("=" * 60)
    logger.info("BACKFILL: Populating customers table and linking trips")
    logger.info("=" * 60)

    # Step 1: Read client data from CSV
    logger.info(f"Reading CSV: {CSV_PATH}")
    df = pd.read_csv(
        CSV_PATH,
        usecols=["i_cnr_id", "s_cnr_name", "i_cne_id", "s_cne_name"],
        low_memory=False,
    )
    logger.info(f"CSV rows: {len(df):,}")

    # Build unique client mapping: cnr_id -> cnr_name (primary client identifier)
    clients = (
        df.dropna(subset=["i_cnr_id", "s_cnr_name"])
        .drop_duplicates(subset=["i_cnr_id"])
        [["i_cnr_id", "s_cnr_name"]]
        .copy()
    )
    clients["i_cnr_id"] = clients["i_cnr_id"].astype(int)
    clients["s_cnr_name"] = clients["s_cnr_name"].str.strip()

    logger.info(f"Unique clients from CSV: {len(clients)}")

    # Step 2: Insert into customers table
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Clear existing (since it's 0 anyway)
            cur.execute("SELECT COUNT(*) AS cnt FROM customers")
            existing = cur.fetchone()["cnt"]
            logger.info(f"Existing customers in DB: {existing}")

            if existing > 0:
                logger.info("Customers already populated, skipping insert")
            else:
                # Insert: use cnr_id as cne_id, cnr_name as cne_name, cnr_name as login_id
                rows = []
                for _, r in clients.iterrows():
                    rows.append((
                        r["s_cnr_name"],           # cne_name (company name)
                        int(r["i_cnr_id"]),         # cne_id (cnr numeric id)
                        str(int(r["i_cnr_id"])),    # cust_login_id (cnr_id as string for lookup)
                    ))

                cur.executemany(
                    "INSERT IGNORE INTO customers (cne_name, cne_id, cust_login_id) VALUES (%s, %s, %s)",
                    rows,
                )
                conn.commit()
                logger.info(f"Inserted {cur.rowcount} customers")

            # Build cnr_id -> customer.id mapping
            cur.execute("SELECT id, cne_id FROM customers WHERE cne_id IS NOT NULL")
            cust_map = {}
            for row in cur.fetchall():
                cust_map[row["cne_id"]] = row["id"]

            logger.info(f"Customer mapping: {len(cust_map)} entries")

        # Step 3: Backfill trips.customer_id using trips.cnr_id
        logger.info("Backfilling trips.customer_id from trips.cnr_id...")

        with conn.cursor() as cur:
            # Check how many trips need updating
            cur.execute("SELECT COUNT(*) AS cnt FROM trips WHERE customer_id IS NULL AND cnr_id IS NOT NULL")
            to_update = cur.fetchone()["cnt"]
            logger.info(f"Trips to update: {to_update:,}")

            if to_update == 0:
                logger.info("All trips already have customer_id, skipping")
                return

            # Update in batches using the cnr_id -> customer mapping
            # Use a JOIN update for efficiency
            cur.execute("""
                UPDATE trips t
                INNER JOIN customers c ON t.cnr_id = c.cne_id
                SET t.customer_id = c.id
                WHERE t.customer_id IS NULL
                  AND t.cnr_id IS NOT NULL
            """)
            updated = cur.rowcount
            conn.commit()
            logger.info(f"Updated {updated:,} trips with customer_id")

            # Verify
            cur.execute("SELECT COUNT(*) AS cnt FROM trips WHERE customer_id IS NOT NULL")
            linked = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM trips WHERE customer_id IS NULL")
            unlinked = cur.fetchone()["cnt"]
            logger.info(f"Trips with customer_id: {linked:,}")
            logger.info(f"Trips without customer_id: {unlinked:,}")

    finally:
        conn.close()

    logger.info("=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
