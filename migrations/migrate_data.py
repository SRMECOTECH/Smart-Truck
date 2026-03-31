"""
Smart-Truck: Data Migration Script
Migrates CSV/Excel trip data + waypoint Excel files → MySQL
Adapted from legacy trip-dispatch-analysis/migrate_updated.py for MySQL 8.0
"""

import sys
import logging
import re
from pathlib import Path

import pandas as pd
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from config.database import get_conn
from config.logging_config import setup_logging

if __name__ == "__main__" or not logging.getLogger().handlers:
    setup_logging(service_name="migrate-data")

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================

BATCH_SIZE = 1000

TRIP_CSV = settings.TRIP_CSV_PATH
WAYPOINT_DIR = settings.WAYPOINT_DIR


# ============================================
# DATA CLEANING UTILITIES
# ============================================

def clean_str(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "nan", "None", "NaN", "NaT", "NA", "na"):
        return None
    return s


def clean_mobile(val):
    s = clean_str(val)
    if s is None:
        return None
    s = s.replace(".0", "")
    s = "".join(c for c in s if c.isdigit() or c == "+")
    if s in ("0", ""):
        return None
    return s


def parse_datetime(val):
    if pd.isna(val):
        return None
    if isinstance(val, str) and val.strip().upper() in ("NAT", "NAN", "NONE", ""):
        return None
    try:
        dt = pd.to_datetime(val, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def safe_float(val):
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
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ============================================
# DATA VALIDATION THRESHOLDS
# ============================================

VALIDATION_RULES = {
    "min_trip_date": pd.Timestamp("2019-01-01"),   # Reject trips before 2019
    "max_distance_km": 5000,                        # Cap distances at 5000 km
    "max_duration_minutes": 14400,                  # Cap durations at 10 days
    "max_speed_kmph": 120,                          # Truck max speed in India
    "min_duration_minutes": 10,                     # Skip ultra-short trips
    "min_distance_km": 1,                           # Skip zero-distance trips
}


def validate_trip_row(trip_start, trip_end, trip_km, total_dist, cover_dist,
                      trip_duration_minutes, avg_speed):
    """Validate and clean a single trip row during migration.
    Returns (is_valid, cleaned_values, is_5am_default, rejection_reason).
    """
    rules = VALIDATION_RULES

    # Reject trips with garbage timestamps
    if trip_start and trip_start < rules["min_trip_date"]:
        return False, {}, 0, "trip_start before 2019"

    # Reject time-travel (arrival before departure)
    if trip_end and trip_start and trip_end < trip_start:
        return False, {}, 0, "ata_in before trip_start"

    # Reject zero-duration trips
    if trip_duration_minutes is not None and trip_duration_minutes == 0:
        return False, {}, 0, "zero duration"

    # Reject negative duration
    if trip_duration_minutes is not None and trip_duration_minutes < 0:
        return False, {}, 0, "negative duration"

    # Detect 5 AM default timestamp
    is_5am_default = 0
    if trip_start and trip_start.hour == 5 and trip_start.minute == 0 and trip_start.second == 0:
        is_5am_default = 1

    # Cap outlier distances
    if trip_km is not None and trip_km > rules["max_distance_km"]:
        trip_km = rules["max_distance_km"]
    if total_dist is not None and total_dist > rules["max_distance_km"]:
        total_dist = rules["max_distance_km"]
    if cover_dist is not None and cover_dist > rules["max_distance_km"]:
        cover_dist = rules["max_distance_km"]

    # Cap outlier duration
    if trip_duration_minutes is not None and trip_duration_minutes > rules["max_duration_minutes"]:
        trip_duration_minutes = rules["max_duration_minutes"]

    # Recompute speed after capping
    if trip_km and trip_duration_minutes and trip_duration_minutes > 0:
        hours = trip_duration_minutes / 60
        avg_speed = round(trip_km / hours, 2)

    # Cap speed
    if avg_speed is not None and avg_speed > rules["max_speed_kmph"]:
        avg_speed = rules["max_speed_kmph"]

    cleaned = {
        "trip_km": trip_km,
        "total_dist": total_dist,
        "cover_dist": cover_dist,
        "trip_duration_minutes": trip_duration_minutes,
        "avg_speed": avg_speed,
    }

    return True, cleaned, is_5am_default, None


# ============================================
# SCHEMA SETUP
# ============================================

def run_schema(conn):
    schema_path = PROJECT_ROOT / "migrations" / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cur:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    cur.execute(statement)
                except pymysql.err.OperationalError as e:
                    # Ignore "index already exists" or "duplicate key name"
                    if e.args[0] in (1061, 1068):
                        continue
                    raise
    conn.commit()
    logger.info("Schema created/verified successfully")


# ============================================
# LOAD TRIP CSV
# ============================================

def load_trip_csv() -> pd.DataFrame:
    if not TRIP_CSV.exists():
        raise FileNotFoundError(f"Trip CSV not found: {TRIP_CSV}")

    logger.info(f"Loading trip CSV: {TRIP_CSV}")
    for encoding in ["utf-8", "latin1", "cp1252"]:
        try:
            df = pd.read_csv(TRIP_CSV, encoding=encoding, low_memory=False)
            break
        except UnicodeDecodeError:
            continue

    logger.info(f"Loaded {len(df):,} rows")

    # The CSV uses these column names from the original source system
    # Map them to what we need:
    # s_dispatch_entry_no → not in this CSV, use i_trip_no as dispatch_entry_no
    # Check which columns exist
    cols = set(df.columns)
    logger.info(f"Columns found: {sorted(cols)}")

    # Deduplicate by i_trip_no
    before = len(df)
    df = df.drop_duplicates(subset=["i_trip_no"], keep="first")
    after = len(df)
    if before > after:
        logger.info(f"Removed {before - after:,} duplicate trip entries")

    return df


# ============================================
# DIMENSION TABLE INSERTS
# ============================================

def insert_drivers(conn, df) -> dict:
    # Extract unique drivers - support both old and new column names
    mobile_col = "s_driver_mob1" if "s_driver_mob1" in df.columns else "s_driver_mobile_no"
    driver_cols = ["s_driver_name", mobile_col]
    drivers = df[driver_cols].drop_duplicates(subset=["s_driver_name", mobile_col])
    drivers = drivers[drivers["s_driver_name"].notna()]

    rows = []
    for _, r in drivers.iterrows():
        name = clean_str(r["s_driver_name"])
        if name is None:
            continue
        mobile1 = clean_mobile(r.get(mobile_col))
        rows.append((name, mobile1))

    if not rows:
        logger.warning("No valid drivers found")
        return {}

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT IGNORE INTO drivers (name, mobile1) VALUES (%s, %s)",
            rows,
        )
    conn.commit()

    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, mobile1 FROM drivers")
        for row in cur.fetchall():
            key = (row["name"], row["mobile1"])
            mapping[key] = row["id"]

    logger.info(f"Drivers: {len(mapping):,} unique")
    return mapping


def insert_vehicles(conn, df) -> dict:
    vehicle_cols = ["s_asset_id", "s_asset_type"]
    vehicles = df[vehicle_cols].drop_duplicates(subset=["s_asset_id"])
    vehicles = vehicles[vehicles["s_asset_id"].notna()]

    rows = []
    for _, r in vehicles.iterrows():
        asset_id = clean_str(r["s_asset_id"])
        if asset_id is None:
            continue
        asset_type = clean_str(r.get("s_asset_type"))
        # trailer_type is s_trip_type_desc in some CSVs
        rows.append((asset_id, asset_type, None))

    if not rows:
        logger.warning("No valid vehicles found")
        return {}

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT IGNORE INTO vehicles (asset_id, asset_type, trailer_type) VALUES (%s, %s, %s)",
            rows,
        )
    conn.commit()

    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, asset_id FROM vehicles")
        for row in cur.fetchall():
            mapping[row["asset_id"]] = row["id"]

    logger.info(f"Vehicles: {len(mapping):,} unique")
    return mapping


def insert_locations(conn, df) -> dict:
    # Support both new (s_origin/s_destination) and legacy (s_org_node_name/s_dest_node_name) columns
    origin_col = "s_origin" if "s_origin" in df.columns else "s_org_node_name"
    dest_col = "s_destination" if "s_destination" in df.columns else "s_dest_node_name"

    origins = set(df[origin_col].dropna().astype(str).str.strip().unique()) if origin_col in df.columns else set()
    destinations = set()
    if dest_col in df.columns:
        destinations = set(df[dest_col].dropna().astype(str).str.strip().unique())
    # Also check s_final_dest
    if "s_final_dest" in df.columns:
        finals = set(df["s_final_dest"].dropna().astype(str).str.strip().unique())
        destinations = destinations | finals

    all_locations = origins | destinations
    all_locations = {loc for loc in all_locations if loc and loc not in ("nan", "None", "NA", "na", "")}

    rows = [(loc,) for loc in sorted(all_locations)]

    if not rows:
        logger.warning("No valid locations found")
        return {}

    with conn.cursor() as cur:
        cur.executemany("INSERT IGNORE INTO locations (name) VALUES (%s)", rows)
    conn.commit()

    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM locations")
        for row in cur.fetchall():
            mapping[row["name"]] = row["id"]

    logger.info(f"Locations: {len(mapping):,} unique")
    return mapping


def insert_customers(conn, df) -> dict:
    cust_cols = ["s_cne_name", "i_cne_id"]
    # Use s_cnr_name as customer login identifier
    if "s_cnr_name" not in df.columns:
        logger.warning("No customer column (s_cnr_name) found")
        return {}

    customers = df[["s_cnr_name", "s_cne_name"]].copy()
    customers["i_cne_id"] = df.get("i_cne_id")
    customers = customers.drop_duplicates(subset=["s_cnr_name"])
    customers = customers[customers["s_cnr_name"].notna()]

    rows = []
    for _, r in customers.iterrows():
        cust_login = clean_str(r["s_cnr_name"])
        if cust_login is None:
            continue
        cne_name = clean_str(r.get("s_cne_name"))
        cne_id = safe_int(r.get("i_cne_id"))
        rows.append((cne_name, cne_id, cust_login))

    if not rows:
        logger.warning("No valid customers found")
        return {}

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT IGNORE INTO customers (cne_name, cne_id, cust_login_id) VALUES (%s, %s, %s)",
            rows,
        )
    conn.commit()

    mapping = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, cust_login_id FROM customers")
        for row in cur.fetchall():
            if row["cust_login_id"]:
                mapping[row["cust_login_id"]] = row["id"]

    logger.info(f"Customers: {len(mapping):,} unique")
    return mapping


# ============================================
# TRIP FACT TABLE INSERT
# ============================================

def _compute_route_avg_km(df) -> dict:
    """Pass 1: Compute average trip_km per route for filling missing values."""
    origin_col = "s_origin" if "s_origin" in df.columns else "s_org_node_name"
    dest_col = "s_destination" if "s_destination" in df.columns else "s_dest_node_name"

    route_km = {}  # (origin, dest) -> list of km values
    for _, r in df.iterrows():
        km = safe_float(r.get("i_trip_km"))
        if km and km > 0:
            o = clean_str(r.get(origin_col))
            d = clean_str(r.get(dest_col))
            if o and d:
                route_km.setdefault((o, d), []).append(km)

    route_avg = {}
    for key, values in route_km.items():
        route_avg[key] = round(sum(values) / len(values), 2)

    filled_count = sum(1 for _, r in df.iterrows()
                       if (safe_float(r.get("i_trip_km")) is None or safe_float(r.get("i_trip_km")) <= 0))
    logger.info(f"Route avg km computed for {len(route_avg)} routes. "
                f"Trips missing km: {filled_count:,} (will fill with route average)")
    return route_avg


def insert_trips(conn, df, driver_map, vehicle_map, location_map, customer_map):
    total = len(df)
    inserted = 0
    skipped = 0

    # Pre-compute route averages for missing km fill
    route_avg_km = _compute_route_avg_km(df)

    # Detect column names (new vs legacy)
    origin_col = "s_origin" if "s_origin" in df.columns else "s_org_node_name"
    dest_col = "s_destination" if "s_destination" in df.columns else "s_dest_node_name"
    mobile_col = "s_driver_mob1" if "s_driver_mob1" in df.columns else "s_driver_mobile_no"

    logger.info(f"Processing {total:,} trip records in batches of {BATCH_SIZE}...")

    rejected = 0

    insert_sql = """
        INSERT IGNORE INTO trips (
            dispatch_entry_no, driver_id, vehicle_id, origin_id, destination_id, customer_id,
            trip_start, trip_end, trip_eta, ata_in, ata_out, dt_created, dt_updated,
            trip_km, total_dist, cover_dist,
            trip_duration_minutes, eta_met, eta_delay_minutes, avg_speed_kmph,
            eta_data_status, is_5am_default,
            trip_status, is_active, trip_close_remark, material_desc,
            invoice_no, invoice_date, ref_no, ref_date,
            entry_type, own_market_type, running_sts, trip_seq, delay_by,
            device_id, device_type, entity_id, cnr_id,
            created_by, updated_by, track_link, data_string
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
    """

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = df.iloc[batch_start:batch_end]
        rows = []

        for idx, r in batch.iterrows():
            try:
                # Use i_trip_no as dispatch_entry_no
                dispatch_no = clean_str(r.get("s_dispatch_entry_no")) or clean_str(r.get("i_trip_no"))
                if dispatch_no is None:
                    skipped += 1
                    continue

                # Resolve foreign keys
                driver_name = clean_str(r.get("s_driver_name"))
                driver_mobile = clean_mobile(r.get(mobile_col))
                driver_id = driver_map.get((driver_name, driver_mobile)) if driver_name else None

                vehicle_id_str = clean_str(r.get("s_asset_id"))
                vehicle_id = vehicle_map.get(vehicle_id_str) if vehicle_id_str else None

                origin_str = clean_str(r.get(origin_col))
                origin_id = location_map.get(origin_str) if origin_str else None

                dest_str = clean_str(r.get(dest_col))
                dest_id = location_map.get(dest_str) if dest_str else None

                cust_login = clean_str(r.get("s_cnr_name") or r.get("s_cust_login_id"))
                customer_id = customer_map.get(cust_login) if cust_login else None

                # Parse timestamps
                trip_start = parse_datetime(r.get("dt_trip_start"))
                trip_end_raw = parse_datetime(r.get("dt_trip_end"))
                trip_eta = parse_datetime(r.get("dt_trip_eta"))
                ata_in = parse_datetime(r.get("dt_ata_in") or r.get("dt_trip_ata"))
                ata_out = parse_datetime(r.get("dt_ata_out"))
                dt_created = parse_datetime(r.get("dt_created"))
                dt_updated = parse_datetime(r.get("dt_updated") or r.get("dt_modified"))

                trip_end = ata_in if ata_in is not None else trip_end_raw

                # eta_data_status flag
                eta_data_status = "available" if ata_in is not None else "eta_data_unavailable"

                # Computed fields
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
                        eta_met = 1 if trip_end <= trip_eta else 0
                        delay = (trip_end - trip_eta).total_seconds() / 60
                        eta_delay_minutes = round(max(0, delay), 2)
                    except Exception:
                        pass

                # Trip km - fill missing with route average
                trip_km = safe_float(r.get("i_trip_km"))
                if (trip_km is None or trip_km <= 0) and origin_str and dest_str:
                    trip_km = route_avg_km.get((origin_str, dest_str))

                total_dist = safe_float(r.get("i_total_dist"))
                cover_dist = safe_float(r.get("i_cover_dist"))

                avg_speed = None
                if trip_km and trip_duration_minutes and trip_duration_minutes > 0:
                    hours = trip_duration_minutes / 60
                    if hours > 0:
                        avg_speed = round(trip_km / hours, 2)

                # ── Validate and clean ──
                is_valid, cleaned, is_5am_default, reason = validate_trip_row(
                    trip_start, trip_end, trip_km, total_dist, cover_dist,
                    trip_duration_minutes, avg_speed,
                )
                if not is_valid:
                    rejected += 1
                    if rejected <= 10:
                        logger.info(f"  Rejected row {idx}: {reason}")
                    continue

                trip_km = cleaned["trip_km"]
                total_dist = cleaned["total_dist"]
                cover_dist = cleaned["cover_dist"]
                trip_duration_minutes = cleaned["trip_duration_minutes"]
                avg_speed = cleaned["avg_speed"]

                rows.append((
                    dispatch_no,
                    driver_id, vehicle_id, origin_id, dest_id, customer_id,
                    trip_start, trip_end, trip_eta, ata_in, ata_out, dt_created, dt_updated,
                    trip_km,
                    total_dist,
                    cover_dist,
                    trip_duration_minutes, eta_met, eta_delay_minutes, avg_speed,
                    eta_data_status, is_5am_default,
                    clean_str(r.get("c_trip_status")),
                    clean_str(r.get("c_is_active")),
                    clean_str(r.get("s_close_reason") or r.get("s_trip_close_remark")),
                    clean_str(r.get("s_material_desc")),
                    clean_str(r.get("s_invoice") or r.get("s_invoice_no")),
                    clean_str(r.get("s_invoice_date")),
                    clean_str(r.get("s_ref_no")),
                    clean_str(r.get("s_ref_date")),
                    clean_str(r.get("s_entry_type") or r.get("s_event_code")),
                    clean_str(r.get("s_own_market_type") or r.get("s_service_provider")),
                    clean_str(r.get("s_running_sts")),
                    safe_int(r.get("i_trip_seq")),
                    safe_float(r.get("i_delay_by")),
                    clean_str(r.get("s_device_id")),
                    clean_str(r.get("s_device_type")),
                    safe_int(r.get("i_entity_id")),
                    safe_int(r.get("i_cnr_id")),
                    clean_str(r.get("s_created_by")),
                    clean_str(r.get("s_modified_by") or r.get("s_updated_by")),
                    clean_str(r.get("s_track_link")),
                    clean_str(r.get("s_data_string") or r.get("s_card_id")),
                ))

            except Exception as e:
                skipped += 1
                if skipped <= 10:
                    logger.warning(f"Row {idx}: {e}")
                continue

        if rows:
            try:
                with conn.cursor() as cur:
                    cur.executemany(insert_sql, rows)
                conn.commit()
                inserted += len(rows)
            except Exception as e:
                logger.error(f"Batch insert error at row {batch_start}: {e}")
                conn.rollback()
                skipped += len(rows)

        progress = (batch_end / total) * 100
        if batch_end % (BATCH_SIZE * 10) == 0 or batch_end == total:
            logger.info(f"  Progress: {batch_end:,}/{total:,} ({progress:.1f}%) | Inserted: {inserted:,} | Skipped: {skipped:,} | Rejected: {rejected:,}")

    logger.info(f"Trip migration complete: {inserted:,} inserted, {skipped:,} skipped, {rejected:,} rejected by validation")
    return inserted, skipped


# ============================================
# WAYPOINT DATA MIGRATION
# ============================================

def load_and_insert_waypoints(conn, vehicle_map):
    if not WAYPOINT_DIR.exists():
        logger.warning(f"Waypoint directory not found: {WAYPOINT_DIR}")
        return

    xls_files = list(WAYPOINT_DIR.glob("Waypoint_*.xls")) + list(WAYPOINT_DIR.glob("Waypoint_*.xlsx"))
    if not xls_files:
        logger.warning("No waypoint files found")
        return

    logger.info(f"Found {len(xls_files)} waypoint files")

    total_inserted = 0

    for filepath in xls_files:
        logger.info(f"Processing waypoint file: {filepath.name}")

        # Extract vehicle asset_id from filename: Waypoint_CG04MC9150.xls → CG04MC9150
        match = re.search(r"Waypoint_(.+)\.(xls|xlsx)$", filepath.name)
        if not match:
            logger.warning(f"  Cannot extract vehicle ID from filename: {filepath.name}")
            continue

        asset_id = match.group(1)
        vehicle_id = vehicle_map.get(asset_id)

        if vehicle_id is None:
            # Insert the vehicle if it doesn't exist
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT IGNORE INTO vehicles (asset_id) VALUES (%s)",
                    (asset_id,),
                )
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM vehicles WHERE asset_id = %s", (asset_id,))
                row = cur.fetchone()
                if row:
                    vehicle_id = row["id"]
                    vehicle_map[asset_id] = vehicle_id

        if vehicle_id is None:
            logger.warning(f"  Could not resolve vehicle: {asset_id}")
            continue

        try:
            df = pd.read_excel(filepath)
        except Exception as e:
            logger.error(f"  Error reading {filepath.name}: {e}")
            continue

        logger.info(f"  Loaded {len(df):,} waypoint rows for vehicle {asset_id}")

        # Expected columns from journey-insights: Asset Number, Date Time, Distance, Status, Latitude, Longitude, Location
        col_map = {}
        for col in df.columns:
            cl = col.lower().strip()
            if "date" in cl and "time" in cl:
                col_map["datetime"] = col
            elif cl in ("distance", "dist"):
                col_map["distance"] = col
            elif cl == "status":
                col_map["status"] = col
            elif cl in ("latitude", "lat"):
                col_map["latitude"] = col
            elif cl in ("longitude", "lon", "lng"):
                col_map["longitude"] = col
            elif cl == "location":
                col_map["location"] = col

        if "datetime" not in col_map:
            logger.warning(f"  No DateTime column found in {filepath.name}. Columns: {list(df.columns)}")
            continue

        insert_sql = """
            INSERT INTO waypoints
            (vehicle_id, latitude, longitude, speed_kmph, status, location_text, distance_from_prev, recorded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        file_inserted = 0
        for batch_start in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[batch_start: batch_start + BATCH_SIZE]
            rows = []

            for _, r in batch.iterrows():
                recorded_at = parse_datetime(r.get(col_map["datetime"]))
                if recorded_at is None:
                    continue

                status_raw = clean_str(r.get(col_map.get("status")))
                speed = None
                if status_raw:
                    # Extract speed from status like "Moving 65" → 65.0
                    speed_match = re.search(r"(\d+\.?\d*)", status_raw)
                    if speed_match and "moving" in status_raw.lower():
                        speed = float(speed_match.group(1))
                    elif "stop" in status_raw.lower():
                        speed = 0.0

                rows.append((
                    vehicle_id,
                    safe_float(r.get(col_map.get("latitude"))),
                    safe_float(r.get(col_map.get("longitude"))),
                    speed,
                    status_raw,
                    clean_str(r.get(col_map.get("location"))),
                    safe_float(r.get(col_map.get("distance"))),
                    recorded_at,
                ))

            if rows:
                with conn.cursor() as cur:
                    cur.executemany(insert_sql, rows)
                conn.commit()
                file_inserted += len(rows)

        logger.info(f"  Inserted {file_inserted:,} waypoints for {asset_id}")
        total_inserted += file_inserted

    logger.info(f"Total waypoints inserted: {total_inserted:,}")


# ============================================
# SUMMARY TABLE REFRESH
# ============================================

def refresh_summaries(conn):
    """Refresh all summary tables. Only uses trips with eta_data_status = 'available'."""
    logger.info("Refreshing summary tables...")

    with conn.cursor() as cur:
        # Driver summary
        cur.execute("DELETE FROM driver_summary")
        cur.execute("""
            INSERT INTO driver_summary
            (driver_id, driver_name, driver_mobile, total_trips, eta_met_count,
             eta_success_rate, avg_duration_min, max_duration_min, min_duration_min,
             avg_speed_kmph, vehicles_used, total_distance_km, avg_distance_km, avg_eta_delay_min)
            SELECT
                d.id, d.name, d.mobile1, COUNT(*),
                SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END),
                ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2),
                ROUND(AVG(t.trip_duration_minutes), 2),
                ROUND(MAX(t.trip_duration_minutes), 2),
                ROUND(MIN(t.trip_duration_minutes), 2),
                ROUND(AVG(t.avg_speed_kmph), 2),
                COUNT(DISTINCT t.vehicle_id),
                ROUND(SUM(t.trip_km), 2),
                ROUND(AVG(t.trip_km), 2),
                ROUND(AVG(t.eta_delay_minutes), 2)
            FROM trips t
            JOIN drivers d ON t.driver_id = d.id
            WHERE t.eta_data_status = 'available'
              AND t.trip_duration_minutes IS NOT NULL
              AND t.trip_duration_minutes > 0
            GROUP BY d.id, d.name, d.mobile1
        """)
    conn.commit()
    logger.info("  Driver summary refreshed")

    with conn.cursor() as cur:
        # Route summary
        cur.execute("DELETE FROM route_summary")
        cur.execute("""
            INSERT INTO route_summary
            (origin, destination, route_name, trip_count, avg_duration_min, avg_speed_kmph, eta_success_rate, avg_distance_km)
            SELECT
                lo.name, ld.name, CONCAT(lo.name, ' -> ', ld.name), COUNT(*),
                ROUND(AVG(t.trip_duration_minutes), 2),
                ROUND(AVG(t.avg_speed_kmph), 2),
                ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2),
                ROUND(AVG(t.trip_km), 2)
            FROM trips t
            JOIN locations lo ON t.origin_id = lo.id
            JOIN locations ld ON t.destination_id = ld.id
            WHERE t.eta_data_status = 'available'
              AND t.trip_duration_minutes IS NOT NULL
              AND t.trip_duration_minutes > 0
            GROUP BY lo.name, ld.name
            ORDER BY COUNT(*) DESC
        """)
    conn.commit()
    logger.info("  Route summary refreshed")

    with conn.cursor() as cur:
        # Vehicle summary
        cur.execute("DELETE FROM vehicle_summary")
        cur.execute("""
            INSERT INTO vehicle_summary
            (vehicle_id, asset_id, asset_type, total_trips, drivers_used,
             avg_speed_kmph, total_distance_km, avg_distance_km, eta_success_rate)
            SELECT
                v.id, v.asset_id, v.asset_type, COUNT(*), COUNT(DISTINCT t.driver_id),
                ROUND(AVG(t.avg_speed_kmph), 2),
                ROUND(SUM(t.trip_km), 2),
                ROUND(AVG(t.trip_km), 2),
                ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2)
            FROM trips t
            JOIN vehicles v ON t.vehicle_id = v.id
            WHERE t.eta_data_status = 'available'
              AND t.trip_duration_minutes IS NOT NULL
              AND t.trip_duration_minutes > 0
            GROUP BY v.id, v.asset_id, v.asset_type
        """)
    conn.commit()
    logger.info("  Vehicle summary refreshed")

    with conn.cursor() as cur:
        # Daily fleet stats
        cur.execute("DELETE FROM daily_fleet_stats")
        cur.execute("""
            INSERT INTO daily_fleet_stats
            (stat_date, total_trips, total_distance_km, avg_speed, eta_success_rate, active_drivers, active_vehicles)
            SELECT
                DATE(t.trip_start), COUNT(*),
                ROUND(SUM(t.trip_km), 2),
                ROUND(AVG(t.avg_speed_kmph), 2),
                ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2),
                COUNT(DISTINCT t.driver_id),
                COUNT(DISTINCT t.vehicle_id)
            FROM trips t
            WHERE t.trip_start IS NOT NULL
              AND t.eta_data_status = 'available'
              AND t.trip_duration_minutes IS NOT NULL
            GROUP BY DATE(t.trip_start)
        """)
    conn.commit()
    logger.info("  Daily fleet stats refreshed")

    with conn.cursor() as cur:
        # Route time patterns
        cur.execute("DELETE FROM route_time_patterns")
        cur.execute("""
            INSERT INTO route_time_patterns
            (origin, destination, hour_of_day, day_of_week, avg_duration, trip_count, eta_success_rate)
            SELECT
                lo.name, ld.name, HOUR(t.trip_start), DAYOFWEEK(t.trip_start),
                ROUND(AVG(t.trip_duration_minutes), 2), COUNT(*),
                ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2)
            FROM trips t
            JOIN locations lo ON t.origin_id = lo.id
            JOIN locations ld ON t.destination_id = ld.id
            WHERE t.trip_start IS NOT NULL
              AND t.trip_duration_minutes IS NOT NULL
              AND t.eta_data_status = 'available'
            GROUP BY lo.name, ld.name, HOUR(t.trip_start), DAYOFWEEK(t.trip_start)
            HAVING COUNT(*) >= 2
        """)
    conn.commit()
    logger.info("  Route time patterns refreshed")

    # Customer summary
    with conn.cursor() as cur:
        cur.execute("DELETE FROM customer_summary")
        cur.execute("""
            INSERT INTO customer_summary
            (customer_id, customer_name, total_trips, total_distance_km, avg_distance_km,
             avg_duration_min, eta_success_rate, unique_routes, unique_drivers, unique_vehicles,
             first_trip_date, last_trip_date, avg_trips_per_week)
            SELECT
                c.id,
                c.cne_name,
                COUNT(*),
                ROUND(SUM(t.trip_km), 2),
                ROUND(AVG(t.trip_km), 2),
                ROUND(AVG(t.trip_duration_minutes), 2),
                ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2),
                COUNT(DISTINCT CONCAT(t.origin_id, '-', t.destination_id)),
                COUNT(DISTINCT t.driver_id),
                COUNT(DISTINCT t.vehicle_id),
                MIN(DATE(t.trip_start)),
                MAX(DATE(t.trip_start)),
                ROUND(COUNT(*) / NULLIF(DATEDIFF(MAX(t.trip_start), MIN(t.trip_start)) / 7.0, 0), 2)
            FROM trips t
            JOIN customers c ON t.customer_id = c.id
            WHERE t.trip_duration_minutes IS NOT NULL
              AND t.trip_duration_minutes > 0
              AND t.eta_data_status = 'available'
            GROUP BY c.id, c.cne_name
        """)
    conn.commit()
    logger.info("  Customer summary refreshed")


# ============================================
# PRINT SUMMARY
# ============================================

def print_summary(conn):
    logger.info("=" * 60)
    logger.info("DATABASE SUMMARY:")
    tables = [
        "drivers", "vehicles", "locations", "customers", "trips",
        "waypoints", "driver_summary", "route_summary", "vehicle_summary",
        "daily_fleet_stats", "route_time_patterns",
    ]
    with conn.cursor() as cur:
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                count = cur.fetchone()["cnt"]
                logger.info(f"  {table:25s}: {count:>10,} rows")
            except Exception as e:
                logger.info(f"  {table:25s}: ERROR ({e})")
    logger.info("=" * 60)


# ============================================
# MAIN
# ============================================

def main():
    logger.info("=" * 60)
    logger.info("Smart-Truck Data Migration → MySQL")
    logger.info("=" * 60)

    # Connect
    logger.info("Connecting to MySQL...")
    conn = get_conn()
    logger.info("Connected to MySQL successfully")

    try:
        # Schema
        logger.info("Setting up schema...")
        run_schema(conn)

        # Load CSV
        df = load_trip_csv()

        # Dimensions
        logger.info("\nInserting dimension tables...")
        driver_map = insert_drivers(conn, df)
        vehicle_map = insert_vehicles(conn, df)
        location_map = insert_locations(conn, df)
        customer_map = insert_customers(conn, df)

        # Trips
        logger.info("\nInserting trip records...")
        inserted, skipped = insert_trips(conn, df, driver_map, vehicle_map, location_map, customer_map)
        logger.info(f"Trips: {inserted:,} inserted, {skipped:,} skipped")

        # Waypoints
        logger.info("\nProcessing waypoint files...")
        load_and_insert_waypoints(conn, vehicle_map)

        # Summaries
        logger.info("\nRefreshing summary tables...")
        refresh_summaries(conn)

        # Summary
        print_summary(conn)

        logger.info("=" * 60)
        logger.info("MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
