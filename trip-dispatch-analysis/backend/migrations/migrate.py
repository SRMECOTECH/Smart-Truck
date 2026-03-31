"""
Migration script: CSV files → Neon PostgreSQL

Reads all CSV files from Data/split_files, deduplicates dimension data,
computes derived fields, and inserts everything into PostgreSQL.
"""

import os
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from config import DATABASE_URL, DATA_DIR
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def load_csvs() -> pd.DataFrame:
    """Load all CSV files from data directory and subdirectories."""
    dfs = []
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.lower().endswith(".csv"):
                path = os.path.join(root, f)
                logger.info(f"Loading {path}")
                df = pd.read_csv(path, low_memory=False)
                dfs.append(df)
                logger.info(f"  → {len(df)} rows")

    if not dfs:
        raise ValueError(f"No CSV files found in {DATA_DIR}")

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Total rows loaded: {len(combined)}")
    return combined


def clean_str(val):
    """Convert to string, strip whitespace, handle NaN."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "nan", "None"):
        return None
    return s


def clean_mobile(val):
    """Clean mobile number - remove .0 suffix from float conversion."""
    s = clean_str(val)
    if s is None:
        return None
    s = s.replace(".0", "")
    if s in ("0", ""):
        return None
    return s


def parse_datetime(val):
    """Parse datetime string, return None on failure."""
    if pd.isna(val):
        return None
    try:
        return pd.to_datetime(val, errors="coerce")
    except Exception:
        return None


def safe_float(val):
    """Convert to float, return None on failure."""
    if pd.isna(val):
        return None
    try:
        v = float(val)
        if np.isinf(v):
            return None
        return v
    except (ValueError, TypeError):
        return None


def safe_int(val):
    """Convert to int, return None on failure."""
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def run_schema(conn):
    """Execute schema.sql to create tables."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, "r") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Schema created successfully")


def insert_drivers(conn, df) -> dict:
    """Insert unique drivers, return name→id mapping."""
    drivers = df[["s_driver_name", "s_driver_mob1", "s_driver_mob2"]].drop_duplicates(subset=["s_driver_name", "s_driver_mob1"])
    drivers = drivers[drivers["s_driver_name"].notna()]

    rows = []
    for _, r in drivers.iterrows():
        name = clean_str(r["s_driver_name"])
        if name is None:
            continue
        mobile1 = clean_mobile(r.get("s_driver_mob1"))
        mobile2 = clean_mobile(r.get("s_driver_mob2"))
        rows.append((name, mobile1, mobile2))

    if not rows:
        return {}

    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO drivers (name, mobile1, mobile2) VALUES %s ON CONFLICT (name, mobile1) DO NOTHING",
            rows
        )
    conn.commit()

    # Build mapping
    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, mobile1 FROM drivers")
        for row in cur.fetchall():
            mapping[(row[1], row[2])] = row[0]

    logger.info(f"Inserted {len(mapping)} unique drivers")
    return mapping


def insert_vehicles(conn, df) -> dict:
    """Insert unique vehicles, return asset_id→id mapping."""
    vehicles = df[["s_asset_id", "s_asset_type", "s_trailer_type"]].drop_duplicates(subset=["s_asset_id"])
    vehicles = vehicles[vehicles["s_asset_id"].notna()]

    rows = []
    for _, r in vehicles.iterrows():
        asset_id = clean_str(r["s_asset_id"])
        if asset_id is None:
            continue
        asset_type = clean_str(r.get("s_asset_type"))
        trailer_type = clean_str(r.get("s_trailer_type"))
        rows.append((asset_id, asset_type, trailer_type))

    if not rows:
        return {}

    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO vehicles (asset_id, asset_type, trailer_type) VALUES %s ON CONFLICT (asset_id) DO NOTHING",
            rows
        )
    conn.commit()

    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, asset_id FROM vehicles")
        for row in cur.fetchall():
            mapping[row[1]] = row[0]

    logger.info(f"Inserted {len(mapping)} unique vehicles")
    return mapping


def insert_locations(conn, df) -> dict:
    """Insert unique locations (origins + destinations), return name→id mapping."""
    origins = set(df["s_origin"].dropna().str.strip().unique())
    destinations = set(df["s_destination"].dropna().str.strip().unique())
    all_locations = origins | destinations
    all_locations.discard("")

    rows = [(loc,) for loc in all_locations if loc]

    if not rows:
        return {}

    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO locations (name) VALUES %s ON CONFLICT (name) DO NOTHING",
            rows
        )
    conn.commit()

    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM locations")
        for row in cur.fetchall():
            mapping[row[1]] = row[0]

    logger.info(f"Inserted {len(mapping)} unique locations")
    return mapping


def insert_customers(conn, df) -> dict:
    """Insert unique customers, return cust_login_id→id mapping."""
    customers = df[["s_cust_login_id", "s_cne_name", "i_cne_id"]].drop_duplicates(subset=["s_cust_login_id"])
    customers = customers[customers["s_cust_login_id"].notna()]

    rows = []
    for _, r in customers.iterrows():
        cust_login = clean_str(r["s_cust_login_id"])
        if cust_login is None:
            continue
        cne_name = clean_str(r.get("s_cne_name"))
        cne_id = safe_int(r.get("i_cne_id"))
        rows.append((cne_name, cne_id, cust_login))

    if not rows:
        return {}

    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO customers (cne_name, cne_id, cust_login_id) VALUES %s ON CONFLICT (cust_login_id) DO NOTHING",
            rows
        )
    conn.commit()

    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, cust_login_id FROM customers")
        for row in cur.fetchall():
            mapping[row[1]] = row[0]

    logger.info(f"Inserted {len(mapping)} unique customers")
    return mapping


def insert_trips(conn, df, driver_map, vehicle_map, location_map, customer_map):
    """Insert trips with foreign keys and computed fields."""
    total = len(df)
    inserted = 0
    skipped = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = df.iloc[batch_start:batch_end]
        rows = []

        for _, r in batch.iterrows():
            dispatch_no = clean_str(r.get("s_dispatch_entry_no"))
            if dispatch_no is None:
                skipped += 1
                continue

            # Resolve foreign keys
            driver_name = clean_str(r.get("s_driver_name"))
            driver_mobile = clean_mobile(r.get("s_driver_mob1"))
            driver_id = driver_map.get((driver_name, driver_mobile)) if driver_name else None

            vehicle_id_str = clean_str(r.get("s_asset_id"))
            vehicle_id = vehicle_map.get(vehicle_id_str) if vehicle_id_str else None

            origin_str = clean_str(r.get("s_origin"))
            origin_id = location_map.get(origin_str) if origin_str else None

            dest_str = clean_str(r.get("s_destination"))
            dest_id = location_map.get(dest_str) if dest_str else None

            cust_login = clean_str(r.get("s_cust_login_id"))
            customer_id = customer_map.get(cust_login) if cust_login else None

            # Parse timestamps
            trip_start = parse_datetime(r.get("dt_trip_start"))
            trip_end_raw = parse_datetime(r.get("dt_trip_end"))
            trip_eta = parse_datetime(r.get("dt_trip_eta"))
            ata_in = parse_datetime(r.get("dt_ata_in"))
            ata_out = parse_datetime(r.get("dt_ata_out"))
            dt_created = parse_datetime(r.get("dt_created"))
            dt_updated = parse_datetime(r.get("dt_updated"))

            # Use ata_in as trip_end (matches analytics.py: dt_ata_in → trip_end)
            trip_end = ata_in

            # Compute derived fields
            trip_duration_minutes = None
            if trip_end is not None and trip_start is not None and pd.notna(trip_end) and pd.notna(trip_start):
                delta = (trip_end - trip_start).total_seconds() / 60
                if delta >= 0:
                    trip_duration_minutes = round(delta, 2)

            eta_met = None
            eta_delay_minutes = None
            if trip_end is not None and trip_eta is not None and pd.notna(trip_end) and pd.notna(trip_eta):
                eta_met = trip_end <= trip_eta
                delay = (trip_end - trip_eta).total_seconds() / 60
                eta_delay_minutes = round(max(0, delay), 2)

            trip_km = safe_float(r.get("i_trip_km"))
            avg_speed = None
            if trip_km is not None and trip_duration_minutes is not None and trip_duration_minutes > 0:
                hours = trip_duration_minutes / 60
                if hours > 0:
                    avg_speed = round(trip_km / hours, 2)

            rows.append((
                dispatch_no,
                driver_id,
                vehicle_id,
                origin_id,
                dest_id,
                customer_id,
                trip_start,
                trip_end,
                trip_eta,
                ata_in,
                ata_out,
                dt_created,
                dt_updated,
                trip_km,
                safe_float(r.get("i_total_dist")),
                safe_float(r.get("i_cover_dist")),
                trip_duration_minutes,
                eta_met,
                eta_delay_minutes,
                avg_speed,
                clean_str(r.get("c_trip_status")),
                clean_str(r.get("c_is_active")),
                clean_str(r.get("s_trip_close_remark")),
                clean_str(r.get("s_material_desc")),
                clean_str(r.get("s_invoice_no")),
                clean_str(r.get("s_invoice_date")),
                clean_str(r.get("s_ref_no")),
                clean_str(r.get("s_ref_date")),
                clean_str(r.get("s_entry_type")),
                clean_str(r.get("s_own_market_type")),
                clean_str(r.get("s_running_sts")),
                safe_int(r.get("i_trip_seq")),
                safe_float(r.get("i_delay_by")),
                clean_str(r.get("s_device_id")),
                clean_str(r.get("s_device_type")),
                safe_int(r.get("i_entity_id")),
                safe_int(r.get("i_cnr_id")),
                clean_str(r.get("s_created_by")),
                clean_str(r.get("s_updated_by")),
                clean_str(r.get("s_track_link")),
                clean_str(r.get("s_data_string")),
            ))

        if rows:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """INSERT INTO trips (
                        dispatch_entry_no, driver_id, vehicle_id, origin_id, destination_id, customer_id,
                        trip_start, trip_end, trip_eta, ata_in, ata_out, dt_created, dt_updated,
                        trip_km, total_dist, cover_dist,
                        trip_duration_minutes, eta_met, eta_delay_minutes, avg_speed_kmph,
                        trip_status, is_active, trip_close_remark, material_desc,
                        invoice_no, invoice_date, ref_no, ref_date,
                        entry_type, own_market_type, running_sts, trip_seq, delay_by,
                        device_id, device_type, entity_id, cnr_id,
                        created_by, updated_by, track_link, data_string
                    ) VALUES %s ON CONFLICT (dispatch_entry_no) DO NOTHING""",
                    rows
                )
            conn.commit()
            inserted += len(rows)

        logger.info(f"Progress: {batch_end}/{total} rows processed ({inserted} inserted, {skipped} skipped)")

    return inserted, skipped


def refresh_materialized_views(conn):
    """Refresh all materialized views after data load."""
    with conn.cursor() as cur:
        logger.info("Refreshing mv_driver_summary...")
        cur.execute("REFRESH MATERIALIZED VIEW mv_driver_summary")
        logger.info("Refreshing mv_route_summary...")
        cur.execute("REFRESH MATERIALIZED VIEW mv_route_summary")
    conn.commit()
    logger.info("Materialized views refreshed")


def print_summary(conn):
    """Print summary counts after migration."""
    with conn.cursor() as cur:
        tables = ["drivers", "vehicles", "locations", "customers", "trips"]
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            logger.info(f"  {table}: {count} rows")


def main():
    logger.info("=" * 60)
    logger.info("Starting migration: CSV → PostgreSQL")
    logger.info("=" * 60)

    # Load CSV data
    df = load_csvs()

    # Connect to database
    logger.info(f"Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)

    try:
        # Create schema
        logger.info("Creating schema...")
        run_schema(conn)

        # Insert dimension tables
        logger.info("Inserting drivers...")
        driver_map = insert_drivers(conn, df)

        logger.info("Inserting vehicles...")
        vehicle_map = insert_vehicles(conn, df)

        logger.info("Inserting locations...")
        location_map = insert_locations(conn, df)

        logger.info("Inserting customers...")
        customer_map = insert_customers(conn, df)

        # Insert trips
        logger.info("Inserting trips...")
        inserted, skipped = insert_trips(conn, df, driver_map, vehicle_map, location_map, customer_map)
        logger.info(f"Trips: {inserted} inserted, {skipped} skipped")

        # Refresh materialized views
        refresh_materialized_views(conn)

        # Print summary
        logger.info("=" * 60)
        logger.info("Migration complete! Summary:")
        print_summary(conn)
        logger.info("=" * 60)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
