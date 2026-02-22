"""
Migration script: CSV/Excel files → Neon PostgreSQL
Version 2.0 - Enhanced with proper NaT handling and analytics

Reads CSV/Excel files, deduplicates dimension data, computes derived fields,
and inserts everything into PostgreSQL.
Handles large datasets (100k+ records) with batch processing.
"""

import os
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from datetime import timedelta
import logging
from pathlib import Path

# Try to import from config.py, fallback to defaults
try:
    from config import DATABASE_URL, DATA_DIR, BATCH_SIZE, LOG_LEVEL
except ImportError:
    # Fallback defaults if config.py doesn't exist
    DATABASE_URL = "postgresql://user:password@host:5432/dbname"  # UPDATE THIS
    DATA_DIR = "Data/split_files"  # UPDATE THIS if needed
    BATCH_SIZE = 1000
    LOG_LEVEL = "INFO"

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Remove the duplicate BATCH_SIZE definition since it comes from config now

# ============================================
# DATA LOADING
# ============================================

def load_data_files() -> pd.DataFrame:
    """Load all CSV and Excel files from data directory."""
    dfs = []
    data_path = Path(DATA_DIR)

    if not data_path.exists():
        raise ValueError(f"Data directory not found: {DATA_DIR}")

    # Find all CSV and Excel files
    csv_files = list(data_path.rglob("*.csv"))
    excel_files = list(data_path.rglob("*.xlsx")) + list(data_path.rglob("*.xls"))

    all_files = csv_files + excel_files

    if not all_files:
        raise ValueError(f"No CSV or Excel files found in {DATA_DIR}")

    logger.info(f"Found {len(csv_files)} CSV and {len(excel_files)} Excel files")

    for file_path in all_files:
        try:
            logger.info(f"Loading {file_path}")

            if file_path.suffix.lower() == '.csv':
                # Try different encodings for CSV
                for encoding in ['utf-8', 'latin1', 'cp1252']:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
                        break
                    except UnicodeDecodeError:
                        continue
            else:
                df = pd.read_excel(file_path)

            logger.info(f"  → {len(df)} rows loaded")
            dfs.append(df)

        except Exception as e:
            logger.error(f"  ✗ Error loading {file_path}: {e}")
            continue

    if not dfs:
        raise ValueError("No data files were successfully loaded")

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Total rows loaded: {len(combined):,}")

    # Remove exact duplicates
    before = len(combined)
    combined = combined.drop_duplicates(subset=['s_dispatch_entry_no'], keep='first')
    after = len(combined)
    if before > after:
        logger.info(f"Removed {before - after:,} duplicate dispatch entries")

    return combined


# ============================================
# DATA CLEANING UTILITIES
# ============================================

def clean_str(val):
    """Convert to string, strip whitespace, handle NaN."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "nan", "None", "NaN", "NaT"):
        return None
    return s


def clean_mobile(val):
    """Clean mobile number - remove .0 suffix from float conversion."""
    s = clean_str(val)
    if s is None:
        return None
    # Remove .0 suffix from floats
    s = s.replace(".0", "")
    # Remove any non-digit characters except +
    s = ''.join(c for c in s if c.isdigit() or c == '+')
    if s in ("0", ""):
        return None
    return s


def parse_datetime(val):
    """Parse datetime string with proper NaT handling."""
    if pd.isna(val):
        return None

    # Handle string 'NaT'
    if isinstance(val, str) and val.strip().upper() in ('NAT', 'NAN', 'NONE', ''):
        return None

    try:
        # Parse with dayfirst=True for DD-MM-YYYY format
        dt = pd.to_datetime(val, dayfirst=True, errors="coerce")

        # Critical: Convert pandas NaT to Python None
        if pd.isna(dt):
            return None

        return dt
    except Exception:
        return None


def safe_float(val):
    """Convert to float, return None on failure."""
    if pd.isna(val):
        return None
    try:
        v = float(val)
        if np.isinf(v) or np.isnan(v):
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


# ============================================
# SCHEMA SETUP
# ============================================

def run_schema(conn):
    """Execute schema.sql to create tables."""
    script_dir = Path(__file__).parent

    # Try schema_updated.sql first (preferred)
    schema_path = script_dir / "schema_updated.sql"

    if not schema_path.exists():
        # Fallback to schema.sql
        schema_path = script_dir / "schema.sql"
        logger.warning("⚠ schema_updated.sql not found, using schema.sql (analytics tables will be missing!)")

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema file not found!\n"
            f"Looked for:\n"
            f"  1. {script_dir / 'schema_updated.sql'}\n"
            f"  2. {script_dir / 'schema.sql'}\n"
            f"Please ensure one of these files exists."
        )

    logger.info(f"Using schema file: {schema_path.name}")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info(f"✓ Schema created successfully from {schema_path.name}")





# ============================================
# DIMENSION TABLE INSERTS
# ============================================

def insert_drivers(conn, df) -> dict:
    """Insert unique drivers, return (name, mobile1) → id mapping."""
    drivers = df[["s_driver_name", "s_driver_mob1", "s_driver_mob2"]].drop_duplicates(
        subset=["s_driver_name", "s_driver_mob1"]
    )
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
        logger.warning("No valid drivers found")
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
            key = (row[1], row[2])
            mapping[key] = row[0]

    logger.info(f"✓ Inserted {len(mapping):,} unique drivers")
    return mapping


def insert_vehicles(conn, df) -> dict:
    """Insert unique vehicles, return asset_id → id mapping."""
    vehicles = df[["s_asset_id", "s_asset_type", "s_trailer_type"]].drop_duplicates(
        subset=["s_asset_id"]
    )
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
        logger.warning("No valid vehicles found")
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

    logger.info(f"✓ Inserted {len(mapping):,} unique vehicles")
    return mapping


def insert_locations(conn, df) -> dict:
    """Insert unique locations (origins + destinations), return name → id mapping."""
    origins = set(df["s_origin"].dropna().astype(str).str.strip().unique())
    destinations = set(df["s_destination"].dropna().astype(str).str.strip().unique())
    all_locations = origins | destinations

    # Remove empty strings and None
    all_locations = {loc for loc in all_locations if loc and loc != 'nan' and loc != 'None'}

    rows = [(loc,) for loc in sorted(all_locations)]

    if not rows:
        logger.warning("No valid locations found")
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

    logger.info(f"✓ Inserted {len(mapping):,} unique locations")
    return mapping


def insert_customers(conn, df) -> dict:
    """Insert unique customers, return cust_login_id → id mapping."""
    customers = df[["s_cust_login_id", "s_cne_name", "i_cne_id"]].drop_duplicates(
        subset=["s_cust_login_id"]
    )
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
        logger.warning("No valid customers found")
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

    logger.info(f"✓ Inserted {len(mapping):,} unique customers")
    return mapping


# ============================================
# TRIP FACT TABLE INSERT
# ============================================

def insert_trips(conn, df, driver_map, vehicle_map, location_map, customer_map):
    """Insert trips with foreign keys and computed fields in batches."""
    total = len(df)
    inserted = 0
    skipped = 0
    errors = []

    logger.info(f"Processing {total:,} trip records in batches of {BATCH_SIZE}...")

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = df.iloc[batch_start:batch_end]
        rows = []

        for idx, r in batch.iterrows():
            try:
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

                # Parse timestamps with proper NaT handling
                trip_start = parse_datetime(r.get("dt_trip_start"))
                trip_end_raw = parse_datetime(r.get("dt_trip_end"))
                trip_eta = parse_datetime(r.get("dt_trip_eta"))
                ata_in = parse_datetime(r.get("dt_ata_in"))
                ata_out = parse_datetime(r.get("dt_ata_out"))
                dt_created = parse_datetime(r.get("dt_created"))
                dt_updated = parse_datetime(r.get("dt_updated"))

                # Use ata_in as trip_end (actual end time)
                trip_end = ata_in if ata_in is not None else trip_end_raw

                # Compute derived fields
                trip_duration_minutes = None
                if trip_end is not None and trip_start is not None:
                    try:
                        delta = (trip_end - trip_start).total_seconds() / 60
                        if delta >= 0:
                            trip_duration_minutes = round(delta, 2)
                    except Exception:
                        pass

                eta_met = None
                eta_delay_minutes = None
                if trip_end is not None and trip_eta is not None:
                    try:
                        eta_met = trip_end <= trip_eta
                        delay = (trip_end - trip_eta).total_seconds() / 60
                        eta_delay_minutes = round(max(0, delay), 2)
                    except Exception:
                        pass

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

            except Exception as e:
                skipped += 1
                errors.append(f"Row {idx}: {str(e)}")
                continue

        # Batch insert
        if rows:
            try:
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
            except Exception as e:
                logger.error(f"Batch insert error: {e}")
                conn.rollback()
                skipped += len(rows)

        # Progress update
        progress = (batch_end / total) * 100
        logger.info(f"  Progress: {batch_end:,}/{total:,} ({progress:.1f}%) | Inserted: {inserted:,} | Skipped: {skipped:,}")

    if errors and len(errors) <= 10:
        logger.warning(f"Sample errors:\n" + "\n".join(errors[:10]))

    return inserted, skipped


# ============================================
# ANALYTICS COMPUTATION
# ============================================

def compute_route_patterns(conn):
    """Compute and store route pattern statistics."""
    logger.info("Computing route patterns...")

    # Check if table exists first
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'route_patterns'
            )
        """)
        table_exists = cur.fetchone()[0]

        if not table_exists:
            logger.warning("⚠ route_patterns table not found - skipping route analytics")
            logger.warning("   To enable: download and use schema_updated.sql")
            return

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO route_patterns (
                origin_id, destination_id, avg_duration_minutes, median_duration_minutes,
                avg_distance_km, avg_speed_kmph, eta_success_rate, sample_size, last_calculated
            )
            SELECT
                origin_id,
                destination_id,
                ROUND(AVG(trip_duration_minutes), 2) AS avg_duration_minutes,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY trip_duration_minutes), 2) AS median_duration_minutes,
                ROUND(AVG(trip_km), 2) AS avg_distance_km,
                ROUND(AVG(avg_speed_kmph), 2) AS avg_speed_kmph,
                ROUND(SUM(CASE WHEN eta_met THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2) AS eta_success_rate,
                COUNT(*) AS sample_size,
                CURRENT_TIMESTAMP AS last_calculated
            FROM trips
            WHERE origin_id IS NOT NULL 
              AND destination_id IS NOT NULL
              AND trip_duration_minutes IS NOT NULL
            GROUP BY origin_id, destination_id
            HAVING COUNT(*) >= 3
            ON CONFLICT (origin_id, destination_id) 
            DO UPDATE SET
                avg_duration_minutes = EXCLUDED.avg_duration_minutes,
                median_duration_minutes = EXCLUDED.median_duration_minutes,
                avg_distance_km = EXCLUDED.avg_distance_km,
                avg_speed_kmph = EXCLUDED.avg_speed_kmph,
                eta_success_rate = EXCLUDED.eta_success_rate,
                sample_size = EXCLUDED.sample_size,
                last_calculated = EXCLUDED.last_calculated
        """)
        rows_affected = cur.rowcount
    conn.commit()
    logger.info(f"✓ Computed {rows_affected:,} route patterns")


def compute_driver_behavior(conn):
    """Compute and store driver behavior analytics."""
    logger.info("Computing driver behavior patterns...")

    # Check if table exists first
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'driver_behavior'
            )
        """)
        table_exists = cur.fetchone()[0]

        if not table_exists:
            logger.warning("⚠ driver_behavior table not found - skipping driver analytics")
            logger.warning("   To enable: download and use schema_updated.sql")
            return

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO driver_behavior (
                driver_id, avg_speed_kmph, speed_consistency, eta_reliability_score,
                avg_trip_duration_minutes, total_trips, total_distance_km,
                preferred_routes, peak_performance_hours, last_calculated
            )
            SELECT
                t.driver_id,
                ROUND(AVG(t.avg_speed_kmph), 2) AS avg_speed_kmph,
                ROUND(STDDEV(t.avg_speed_kmph), 2) AS speed_consistency,
                ROUND(SUM(CASE WHEN t.eta_met THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2) AS eta_reliability_score,
                ROUND(AVG(t.trip_duration_minutes), 2) AS avg_trip_duration_minutes,
                COUNT(*) AS total_trips,
                ROUND(SUM(t.trip_km), 2) AS total_distance_km,
                ARRAY(
                    SELECT lo.name || ' → ' || ld.name
                    FROM trips t2
                    JOIN locations lo ON t2.origin_id = lo.id
                    JOIN locations ld ON t2.destination_id = ld.id
                    WHERE t2.driver_id = t.driver_id
                    GROUP BY lo.name, ld.name
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                ) AS preferred_routes,
                ARRAY(
                    SELECT EXTRACT(HOUR FROM trip_start)::INTEGER
                    FROM trips t3
                    WHERE t3.driver_id = t.driver_id 
                      AND t3.eta_met = TRUE
                    GROUP BY EXTRACT(HOUR FROM trip_start)
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                ) AS peak_performance_hours,
                CURRENT_TIMESTAMP AS last_calculated
            FROM trips t
            WHERE t.driver_id IS NOT NULL
              AND t.trip_start IS NOT NULL
            GROUP BY t.driver_id
            HAVING COUNT(*) >= 5
            ON CONFLICT (driver_id)
            DO UPDATE SET
                avg_speed_kmph = EXCLUDED.avg_speed_kmph,
                speed_consistency = EXCLUDED.speed_consistency,
                eta_reliability_score = EXCLUDED.eta_reliability_score,
                avg_trip_duration_minutes = EXCLUDED.avg_trip_duration_minutes,
                total_trips = EXCLUDED.total_trips,
                total_distance_km = EXCLUDED.total_distance_km,
                preferred_routes = EXCLUDED.preferred_routes,
                peak_performance_hours = EXCLUDED.peak_performance_hours,
                last_calculated = EXCLUDED.last_calculated
        """)
        rows_affected = cur.rowcount
    conn.commit()
    logger.info(f"✓ Computed behavior for {rows_affected:,} drivers")


def refresh_materialized_views(conn):
    """Refresh all materialized views after data load."""
    views = ["mv_driver_summary", "mv_route_summary", "mv_time_analysis", "mv_driver_routes"]

    for view in views:
        try:
            # Check if view exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM pg_matviews
                        WHERE matviewname = %s
                    )
                """, (view,))
                exists = cur.fetchone()[0]

                if not exists:
                    logger.warning(f"⚠ {view} not found - skipping")
                    continue

            logger.info(f"Refreshing {view}...")
            with conn.cursor() as cur:
                cur.execute(f"REFRESH MATERIALIZED VIEW {view}")
            conn.commit()
            logger.info(f"✓ {view} refreshed")
        except Exception as e:
            logger.error(f"✗ Error refreshing {view}: {e}")


# ============================================
# SUMMARY & STATS
# ============================================

def print_summary(conn):
    """Print summary counts after migration."""
    logger.info("=" * 60)
    logger.info("DATABASE SUMMARY:")

    tables = [
        "drivers", "vehicles", "locations", "customers", "trips",
        "route_patterns", "driver_behavior"
    ]

    with conn.cursor() as cur:
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                logger.info(f"  {table:20s}: {count:,} rows")
            except Exception as e:
                logger.info(f"  {table:20s}: N/A ({e})")

    logger.info("=" * 60)


# ============================================
# MAIN EXECUTION
# ============================================

def main():
    logger.info("=" * 60)
    logger.info("Trip Analytics - Data Migration Tool v2.0")
    logger.info("=" * 60)

    # Step 1: Load data
    try:
        df = load_data_files()
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return

    # Step 2: Connect to database
    logger.info(f"Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("✓ Connected successfully")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return

    try:
        # Step 3: Create schema
        logger.info("Creating database schema...")
        run_schema(conn)

        # Step 4: Insert dimension tables
        logger.info("\nInserting dimension tables...")
        driver_map = insert_drivers(conn, df)
        vehicle_map = insert_vehicles(conn, df)
        location_map = insert_locations(conn, df)
        customer_map = insert_customers(conn, df)

        # Step 5: Insert trips (fact table)
        logger.info("\nInserting trip records...")
        inserted, skipped = insert_trips(conn, df, driver_map, vehicle_map, location_map, customer_map)
        logger.info(f"✓ Trips complete: {inserted:,} inserted, {skipped:,} skipped")

        # Step 6: Compute analytics
        logger.info("\nComputing analytics...")
        compute_route_patterns(conn)
        compute_driver_behavior(conn)

        # Step 7: Refresh materialized views
        logger.info("\nRefreshing materialized views...")
        refresh_materialized_views(conn)

        # Step 8: Print summary
        print_summary(conn)

        logger.info("=" * 60)
        logger.info("✓ MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    main()