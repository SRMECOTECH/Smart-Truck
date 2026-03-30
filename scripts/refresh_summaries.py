"""
Standalone script to refresh all summary tables in MySQL.
Supports two modes:
  - Full refresh (default): DELETE + re-INSERT all summary data
  - Incremental refresh (--incremental): Only update drivers/routes/vehicles
    that have new trips since last refresh

Usage:
  python scripts/refresh_summaries.py              # Full refresh
  python scripts/refresh_summaries.py --incremental # Incremental (faster for large DBs)
"""

import sys
import argparse
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.database import get_conn
from config.logging_config import setup_logging

setup_logging(service_name="refresh-summaries")
logger = logging.getLogger(__name__)


def refresh_full(conn):
    """Full refresh — delete all and re-insert."""
    from migrations.migrate_data import refresh_summaries
    refresh_summaries(conn)


def refresh_incremental(conn):
    """
    Incremental refresh — only update drivers/routes/vehicles that have
    new trips since the last summary refresh. Much faster for large DBs.
    """
    logger.info("Starting incremental summary refresh...")

    with conn.cursor() as cur:
        # Find the latest refresh timestamp across summary tables
        cur.execute("SELECT MAX(last_refreshed) AS lr FROM driver_summary")
        row = cur.fetchone()
        last_refreshed = row["lr"] if row and row["lr"] else "2000-01-01"
        logger.info(f"Last refresh: {last_refreshed}")

        # Find drivers with new trips since last refresh
        cur.execute("""
            SELECT DISTINCT driver_id FROM trips
            WHERE dt_created > %s OR dt_updated > %s
              AND driver_id IS NOT NULL
              AND trip_duration_minutes > 0
              AND eta_data_status = 'available'
        """, (last_refreshed, last_refreshed))
        changed_drivers = [r["driver_id"] for r in cur.fetchall()]
        logger.info(f"Drivers with new data: {len(changed_drivers)}")

        # Find routes with new trips
        cur.execute("""
            SELECT DISTINCT origin_id, destination_id FROM trips
            WHERE dt_created > %s OR dt_updated > %s
              AND origin_id IS NOT NULL AND destination_id IS NOT NULL
              AND trip_duration_minutes > 0
              AND eta_data_status = 'available'
        """, (last_refreshed, last_refreshed))
        changed_routes = cur.fetchall()
        logger.info(f"Routes with new data: {len(changed_routes)}")

        # Find vehicles with new trips
        cur.execute("""
            SELECT DISTINCT vehicle_id FROM trips
            WHERE dt_created > %s OR dt_updated > %s
              AND vehicle_id IS NOT NULL
              AND trip_duration_minutes > 0
              AND eta_data_status = 'available'
        """, (last_refreshed, last_refreshed))
        changed_vehicles = [r["vehicle_id"] for r in cur.fetchall()]
        logger.info(f"Vehicles with new data: {len(changed_vehicles)}")

    if not changed_drivers and not changed_routes and not changed_vehicles:
        logger.info("No new data since last refresh. Skipping.")
        return

    # ── Update driver summaries ──────────────────────────────────────────
    if changed_drivers:
        _refresh_drivers_incremental(conn, changed_drivers)

    # ── Update route summaries ───────────────────────────────────────────
    if changed_routes:
        _refresh_routes_incremental(conn, changed_routes)

    # ── Update vehicle summaries ─────────────────────────────────────────
    if changed_vehicles:
        _refresh_vehicles_incremental(conn, changed_vehicles)

    # ── Always full-refresh daily stats, time patterns, customer summary ──
    # (they're date-based or small enough, full refresh is fast enough)
    _refresh_daily_stats(conn)
    _refresh_time_patterns(conn)
    _refresh_customer_summary(conn)

    logger.info("Incremental refresh complete!")


def _refresh_drivers_incremental(conn, driver_ids: list):
    """Update summary for specific drivers only."""
    if not driver_ids:
        return

    # Process in batches of 500
    batch_size = 500
    for i in range(0, len(driver_ids), batch_size):
        batch = driver_ids[i:i + batch_size]
        placeholders = ",".join(["%s"] * len(batch))

        with conn.cursor() as cur:
            # Delete old rows for these drivers
            cur.execute(f"DELETE FROM driver_summary WHERE driver_id IN ({placeholders})", batch)

            # Re-insert
            cur.execute(f"""
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
                  AND d.id IN ({placeholders})
                GROUP BY d.id, d.name, d.mobile1
            """, batch)
        conn.commit()

    logger.info(f"  Updated {len(driver_ids)} driver summaries")


def _refresh_routes_incremental(conn, changed_routes: list):
    """Update summary for specific routes only."""
    if not changed_routes:
        return

    for route in changed_routes:
        oid = route["origin_id"]
        did = route["destination_id"]

        with conn.cursor() as cur:
            # Get location names
            cur.execute("SELECT name FROM locations WHERE id = %s", (oid,))
            origin_row = cur.fetchone()
            cur.execute("SELECT name FROM locations WHERE id = %s", (did,))
            dest_row = cur.fetchone()

            if not origin_row or not dest_row:
                continue

            origin = origin_row["name"]
            dest = dest_row["name"]

            # Delete and re-insert
            cur.execute("DELETE FROM route_summary WHERE origin = %s AND destination = %s", (origin, dest))
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
                WHERE lo.name = %s AND ld.name = %s
                  AND t.eta_data_status = 'available'
                  AND t.trip_duration_minutes IS NOT NULL
                  AND t.trip_duration_minutes > 0
                GROUP BY lo.name, ld.name
            """, (origin, dest))
        conn.commit()

    logger.info(f"  Updated {len(changed_routes)} route summaries")


def _refresh_vehicles_incremental(conn, vehicle_ids: list):
    """Update summary for specific vehicles only."""
    if not vehicle_ids:
        return

    batch_size = 500
    for i in range(0, len(vehicle_ids), batch_size):
        batch = vehicle_ids[i:i + batch_size]
        placeholders = ",".join(["%s"] * len(batch))

        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM vehicle_summary WHERE vehicle_id IN ({placeholders})", batch)
            cur.execute(f"""
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
                  AND v.id IN ({placeholders})
                GROUP BY v.id, v.asset_id, v.asset_type
            """, batch)
        conn.commit()

    logger.info(f"  Updated {len(vehicle_ids)} vehicle summaries")


def _refresh_customer_summary(conn):
    """Full refresh of customer summary table."""
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


def _refresh_daily_stats(conn):
    """Full refresh of daily fleet stats (fast since it's date-grouped)."""
    with conn.cursor() as cur:
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


def _refresh_time_patterns(conn):
    """Full refresh of route time patterns."""
    with conn.cursor() as cur:
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


def main():
    parser = argparse.ArgumentParser(description="Refresh summary tables")
    parser.add_argument("--incremental", "-i", action="store_true",
                        help="Incremental refresh (only changed entities)")
    args = parser.parse_args()

    conn = get_conn()
    try:
        if args.incremental:
            logger.info("Running INCREMENTAL summary refresh...")
            refresh_incremental(conn)
        else:
            logger.info("Running FULL summary refresh...")
            refresh_full(conn)
        logger.info("All summaries refreshed!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
