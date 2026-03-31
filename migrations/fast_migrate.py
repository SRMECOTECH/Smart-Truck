"""
Fast migration: Pre-process CSV in pandas, then bulk-load via LOAD DATA LOCAL INFILE.
~20-50x faster than row-by-row INSERT for 7.4M rows.
"""

import os
import sys
import re
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from config.database import get_conn as _base_get_conn
from config.logging_config import setup_logging

setup_logging(service_name="fast-migrate")
logger = logging.getLogger(__name__)

TRIP_CSV = PROJECT_ROOT / "data-analysis" / "data" / "tbl_trip_data20260128.csv"
WAYPOINT_DIR = PROJECT_ROOT / "journey-insights" / "Datasets"
TEMP_DIR = PROJECT_ROOT / "migrations" / "temp"
TEMP_DIR.mkdir(exist_ok=True)


def get_conn():
    return _base_get_conn(local_infile=True)


def enable_local_infile(conn):
    """Enable LOAD DATA LOCAL INFILE on server side."""
    with conn.cursor() as cur:
        cur.execute("SET GLOBAL local_infile = 1")
    conn.commit()


# ============================================
# STEP 1: Build FK lookup maps from existing dimension tables
# ============================================

def build_lookup_maps(conn):
    logger.info("Building FK lookup maps from dimension tables...")

    with conn.cursor() as cur:
        cur.execute("SELECT id, name, mobile1 FROM drivers")
        driver_map = {}
        for r in cur.fetchall():
            driver_map[(r["name"], r["mobile1"])] = r["id"]
        logger.info(f"  Driver map: {len(driver_map):,} entries")

        cur.execute("SELECT id, asset_id FROM vehicles")
        vehicle_map = {r["asset_id"]: r["id"] for r in cur.fetchall()}
        logger.info(f"  Vehicle map: {len(vehicle_map):,} entries")

        cur.execute("SELECT id, name FROM locations")
        location_map = {r["name"]: r["id"] for r in cur.fetchall()}
        logger.info(f"  Location map: {len(location_map):,} entries")

        cur.execute("SELECT id, cust_login_id FROM customers")
        customer_map = {r["cust_login_id"]: r["id"] for r in cur.fetchall() if r["cust_login_id"]}
        logger.info(f"  Customer map: {len(customer_map):,} entries")

    return driver_map, vehicle_map, location_map, customer_map


# ============================================
# STEP 2: Pre-process CSV in pandas (vectorized = fast)
# ============================================

def clean_mobile_series(s):
    """Vectorized mobile cleaning."""
    s = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    s = s.str.replace(r"[^\d+]", "", regex=True)
    s = s.replace({"0": None, "": None, "nan": None, "None": None})
    return s


def preprocess_trips(df, driver_map, vehicle_map, location_map, customer_map):
    logger.info("Pre-processing trip data (vectorized)...")
    start = datetime.now()

    # Clean string columns
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "NaN": None, "NA": None, "": None, "NaT": None})

    # Dispatch entry number
    df["dispatch_entry_no"] = df["i_trip_no"].astype(str).str.strip()

    # Resolve driver FK
    df["driver_mobile_clean"] = clean_mobile_series(df["s_driver_mobile_no"])
    df["driver_key"] = list(zip(df["s_driver_name"], df["driver_mobile_clean"]))
    df["driver_id"] = df["driver_key"].map(driver_map)

    # Resolve vehicle FK
    df["vehicle_id"] = df["s_asset_id"].map(vehicle_map)

    # Resolve location FKs
    df["origin_id"] = df["s_org_node_name"].map(location_map)
    df["destination_id"] = df["s_dest_node_name"].map(location_map)

    # Resolve customer FK
    df["customer_id"] = df["s_cnr_name"].map(customer_map)

    # Parse timestamps
    ts_cols = ["dt_trip_start", "dt_trip_eta", "dt_trip_ata", "dt_trip_end", "dt_created", "dt_modified"]
    for col in ts_cols:
        if col in df.columns:
            df[col + "_parsed"] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # trip_end = ata if available, else dt_trip_end
    df["trip_end_final"] = df["dt_trip_ata_parsed"].fillna(df["dt_trip_end_parsed"])

    # Computed: trip_duration_minutes
    valid_times = df["trip_end_final"].notna() & df["dt_trip_start_parsed"].notna()
    df["trip_duration_minutes"] = np.where(
        valid_times,
        (df["trip_end_final"] - df["dt_trip_start_parsed"]).dt.total_seconds() / 60,
        None,
    )
    # Remove negative durations
    df.loc[df["trip_duration_minutes"] is not None, "trip_duration_minutes"] = (
        df["trip_duration_minutes"].where(df["trip_duration_minutes"] >= 0)
    )

    # Computed: eta_met
    valid_eta = df["trip_end_final"].notna() & df["dt_trip_eta_parsed"].notna()
    df["eta_met"] = np.where(
        valid_eta,
        (df["trip_end_final"] <= df["dt_trip_eta_parsed"]).astype(int),
        None,
    )

    # Computed: eta_delay_minutes
    df["eta_delay_minutes"] = np.where(
        valid_eta,
        np.maximum(0, (df["trip_end_final"] - df["dt_trip_eta_parsed"]).dt.total_seconds() / 60),
        None,
    )

    # avg_speed (trip_km not in this CSV, so will be NULL)
    df["avg_speed_kmph"] = None

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"Pre-processing done in {elapsed:.1f}s")
    return df


# ============================================
# STEP 3: Write clean CSV for LOAD DATA INFILE
# ============================================

def write_bulk_csv(df):
    logger.info("Writing bulk CSV for LOAD DATA INFILE...")

    output_path = TEMP_DIR / "trips_bulk.csv"

    # Format datetime columns
    def fmt_dt(col):
        return df[col].dt.strftime("%Y-%m-%d %H:%M:%S").where(df[col].notna(), other="\\N")

    bulk = pd.DataFrame({
        "dispatch_entry_no": df["dispatch_entry_no"],
        "driver_id": df["driver_id"],
        "vehicle_id": df["vehicle_id"],
        "origin_id": df["origin_id"],
        "destination_id": df["destination_id"],
        "customer_id": df["customer_id"],
        "trip_start": fmt_dt("dt_trip_start_parsed"),
        "trip_end": fmt_dt("trip_end_final"),
        "trip_eta": fmt_dt("dt_trip_eta_parsed"),
        "ata_in": fmt_dt("dt_trip_ata_parsed"),
        "ata_out": "\\N",  # not in this CSV
        "dt_created": fmt_dt("dt_created_parsed"),
        "dt_updated": fmt_dt("dt_modified_parsed"),
        "trip_km": "\\N",
        "total_dist": "\\N",
        "cover_dist": "\\N",
        "trip_duration_minutes": df["trip_duration_minutes"],
        "eta_met": df["eta_met"],
        "eta_delay_minutes": df["eta_delay_minutes"],
        "avg_speed_kmph": "\\N",
        "trip_status": df["c_trip_status"],
        "is_active": df["c_is_active"],
        "trip_close_remark": df["s_close_reason"],
        "material_desc": "\\N",
        "invoice_no": df["s_invoice"],
        "invoice_date": "\\N",
        "ref_no": "\\N",
        "ref_date": "\\N",
        "entry_type": df["s_event_code"],
        "own_market_type": df["s_service_provider"],
        "running_sts": "\\N",
        "trip_seq": "\\N",
        "delay_by": "\\N",
        "device_id": df["s_device_id"],
        "device_type": "\\N",
        "entity_id": "\\N",
        "cnr_id": df["i_cnr_id"],
        "created_by": df["s_created_by"],
        "updated_by": df["s_modified_by"],
        "track_link": "\\N",
        "data_string": df["s_card_id"],
    })

    # Replace NaN/None with \N (MySQL NULL marker)
    bulk = bulk.fillna("\\N")

    # Replace "None" strings
    bulk = bulk.replace({"None": "\\N", "nan": "\\N", "NaT": "\\N"})

    bulk.to_csv(output_path, index=False, header=False, sep="\t", na_rep="\\N")

    file_size = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Bulk CSV written: {output_path} ({file_size:.1f} MB, {len(bulk):,} rows)")
    return output_path


# ============================================
# STEP 4: LOAD DATA LOCAL INFILE
# ============================================

def bulk_load_trips(conn, csv_path):
    logger.info("Bulk loading trips via LOAD DATA LOCAL INFILE...")
    start = datetime.now()

    # First, clear existing trips (from the slow migration)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM trips")
        existing = cur.fetchone()["cnt"]
        if existing > 0:
            logger.info(f"  Clearing {existing:,} existing trip rows...")
            cur.execute("DELETE FROM trips")
            conn.commit()
            logger.info("  Cleared.")

    # Use forward slashes for MySQL path
    csv_path_str = str(csv_path).replace("\\", "/")

    load_sql = f"""
        LOAD DATA LOCAL INFILE '{csv_path_str}'
        INTO TABLE trips
        FIELDS TERMINATED BY '\\t'
        LINES TERMINATED BY '\\n'
        (dispatch_entry_no, driver_id, vehicle_id, origin_id, destination_id, customer_id,
         trip_start, trip_end, trip_eta, ata_in, ata_out, dt_created, dt_updated,
         trip_km, total_dist, cover_dist,
         trip_duration_minutes, eta_met, eta_delay_minutes, avg_speed_kmph,
         trip_status, is_active, trip_close_remark, material_desc,
         invoice_no, invoice_date, ref_no, ref_date,
         entry_type, own_market_type, running_sts, trip_seq, delay_by,
         device_id, device_type, entity_id, cnr_id,
         created_by, updated_by, track_link, data_string)
    """

    with conn.cursor() as cur:
        cur.execute(load_sql)
    conn.commit()

    # Check count
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM trips")
        count = cur.fetchone()["cnt"]

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"Loaded {count:,} trips in {elapsed:.1f}s")
    return count


# ============================================
# STEP 5: Waypoints
# ============================================

def load_waypoints(conn, vehicle_map):
    if not WAYPOINT_DIR.exists():
        logger.warning(f"Waypoint directory not found: {WAYPOINT_DIR}")
        return

    xls_files = list(WAYPOINT_DIR.glob("Waypoint_*.xls")) + list(WAYPOINT_DIR.glob("Waypoint_*.xlsx"))
    if not xls_files:
        logger.warning("No waypoint files found")
        return

    logger.info(f"Found {len(xls_files)} waypoint files")
    total = 0

    for fp in xls_files:
        match = re.search(r"Waypoint_(.+)\.(xls|xlsx)$", fp.name)
        if not match:
            continue

        asset_id = match.group(1)
        vid = vehicle_map.get(asset_id)

        if vid is None:
            with conn.cursor() as cur:
                cur.execute("INSERT IGNORE INTO vehicles (asset_id) VALUES (%s)", (asset_id,))
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM vehicles WHERE asset_id = %s", (asset_id,))
                row = cur.fetchone()
                if row:
                    vid = row["id"]
                    vehicle_map[asset_id] = vid

        if vid is None:
            continue

        try:
            df = pd.read_excel(fp)
        except Exception as e:
            logger.error(f"Error reading {fp.name}: {e}")
            continue

        logger.info(f"  {fp.name}: {len(df):,} rows")

        # Find columns
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
            continue

        df["recorded_at"] = pd.to_datetime(df[col_map["datetime"]], errors="coerce")
        df = df[df["recorded_at"].notna()]

        if "status" in col_map:
            status_col = df[col_map["status"]].astype(str).str.strip()
            speed = status_col.str.extract(r"(\d+\.?\d*)", expand=False).astype(float)
            speed = speed.where(status_col.str.lower().str.contains("moving", na=False), 0.0)
        else:
            status_col = None
            speed = None

        rows = []
        for _, r in df.iterrows():
            rows.append((
                vid,
                float(r.get(col_map.get("latitude"), None)) if col_map.get("latitude") and pd.notna(r.get(col_map["latitude"])) else None,
                float(r.get(col_map.get("longitude"), None)) if col_map.get("longitude") and pd.notna(r.get(col_map["longitude"])) else None,
                float(speed.iloc[_]) if speed is not None and pd.notna(speed.iloc[_]) else None,
                str(r.get(col_map.get("status"), "")) if col_map.get("status") and pd.notna(r.get(col_map["status"])) else None,
                str(r.get(col_map.get("location"), "")) if col_map.get("location") and pd.notna(r.get(col_map["location"])) else None,
                float(r.get(col_map.get("distance"), None)) if col_map.get("distance") and pd.notna(r.get(col_map["distance"])) else None,
                r["recorded_at"].to_pydatetime(),
            ))

        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO waypoints
                    (vehicle_id, latitude, longitude, speed_kmph, status, location_text, distance_from_prev, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    rows,
                )
            conn.commit()
            total += len(rows)
            logger.info(f"    Inserted {len(rows):,} waypoints")

    logger.info(f"Total waypoints: {total:,}")


# ============================================
# STEP 6: Refresh summaries
# ============================================

def refresh_summaries(conn):
    from migrations.migrate_data import refresh_summaries as _refresh
    _refresh(conn)


# ============================================
# MAIN
# ============================================

def main():
    logger.info("=" * 60)
    logger.info("FAST Migration: CSV → MySQL (LOAD DATA INFILE)")
    logger.info("=" * 60)

    total_start = datetime.now()

    # Connect
    conn = get_conn()
    enable_local_infile(conn)

    try:
        # Build lookups from already-loaded dimension tables
        driver_map, vehicle_map, location_map, customer_map = build_lookup_maps(conn)

        # Load CSV
        logger.info(f"Loading CSV: {TRIP_CSV}")
        df = pd.read_csv(TRIP_CSV, encoding="utf-8", low_memory=False)
        logger.info(f"Loaded {len(df):,} rows")

        # Dedup
        before = len(df)
        df = df.drop_duplicates(subset=["i_trip_no"], keep="first")
        logger.info(f"After dedup: {len(df):,} rows (removed {before - len(df):,})")

        # Pre-process
        df = preprocess_trips(df, driver_map, vehicle_map, location_map, customer_map)

        # Write bulk CSV
        csv_path = write_bulk_csv(df)

        # Bulk load
        count = bulk_load_trips(conn, csv_path)

        # Waypoints
        logger.info("\nLoading waypoints...")
        load_waypoints(conn, vehicle_map)

        # Refresh summaries
        logger.info("\nRefreshing summary tables...")
        refresh_summaries(conn)

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("FINAL COUNTS:")
        with conn.cursor() as cur:
            for table in ["drivers", "vehicles", "locations", "customers", "trips",
                          "waypoints", "driver_summary", "route_summary",
                          "vehicle_summary", "daily_fleet_stats"]:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                c = cur.fetchone()["cnt"]
                logger.info(f"  {table:25s}: {c:>10,}")

        total_elapsed = (datetime.now() - total_start).total_seconds()
        logger.info(f"\nTotal time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
        logger.info("=" * 60)

        # Cleanup temp file
        csv_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
