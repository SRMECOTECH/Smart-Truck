import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from backend.app.core.database import get_db
from backend.app.schemas.driver import DriverSummaryOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drivers", tags=["Drivers"])


def _compute_scores(rows: list) -> list:
    """Compute composite driver score for every row using Bayesian-smoothed ETA
    + experience + speed safety.  Same formula as ml_service driver_scorer."""
    if not rows:
        return rows

    # Global priors
    all_eta = [float(r.get("eta_success_rate") or 0) for r in rows]
    all_trips = [int(r.get("total_trips") or 0) for r in rows]
    all_speed = [float(r.get("avg_speed_kmph") or 0) for r in rows]

    global_eta_avg = sum(all_eta) / len(all_eta) if all_eta else 55.0
    max_trips = max(all_trips) if all_trips else 1
    confidence_trips = 15.0  # Bayesian smoothing constant

    for r in rows:
        eta_raw = float(r.get("eta_success_rate") or 0)
        n_trips = int(r.get("total_trips") or 0)
        speed = float(r.get("avg_speed_kmph") or 0)

        # 1. Bayesian-smoothed ETA (0-100)
        eta_score = (n_trips * eta_raw + confidence_trips * global_eta_avg) / (n_trips + confidence_trips)

        # 2. Experience (0-100) — log-scaled so diminishing returns
        import math as _m
        exp_score = min(100, (_m.log1p(n_trips) / _m.log1p(max_trips)) * 100) if max_trips > 0 else 0

        # 3. Speed safety (0-100) — ideal 20-40 km/h for trucks
        if 20 <= speed <= 40:
            speed_score = 100.0
        elif speed < 20:
            speed_score = max(0, speed / 20 * 100)
        else:
            speed_score = max(0, 100 - (speed - 40) * 2.5)

        # Composite: ETA 35%, Experience 25%, Speed 20%, base 20% (ETA raw scaled)
        composite = (
            eta_score * 0.35
            + exp_score * 0.25
            + speed_score * 0.20
            + min(eta_raw, 100) * 0.20
        )
        r["composite_score"] = round(composite, 1)

    return rows


@router.get("")
def list_drivers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: str = "total_trips",
    sort_order: str = "desc",
    conn=Depends(get_db),
):
    offset = (page - 1) * limit
    allowed_sorts = {
        "total_trips", "eta_success_rate", "avg_speed_kmph",
        "total_distance_km", "driver_name", "avg_duration_min",
    }
    if sort_by not in allowed_sorts:
        sort_by = "total_trips"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    where = ""
    params = []
    if search:
        where = "WHERE driver_name LIKE %s OR driver_mobile LIKE %s"
        params = [f"%{search}%", f"%{search}%"]

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM driver_summary {where}", params)
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT driver_id, driver_name, driver_mobile, total_trips,
                   eta_met_count, eta_success_rate, avg_duration_min,
                   max_duration_min, min_duration_min, avg_speed_kmph,
                   vehicles_used, total_distance_km, avg_distance_km, avg_eta_delay_min
            FROM driver_summary
            {where}
            ORDER BY {sort_by} {sort_order}
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

    # Compute composite score for every driver in the page
    rows = _compute_scores(rows)

    return {
        "data": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit) if limit else 0,
    }


@router.get("/{driver_id}")
def get_driver_detail(driver_id: int, conn=Depends(get_db)):
    with conn.cursor() as cur:
        # Driver summary
        cur.execute(
            "SELECT * FROM driver_summary WHERE driver_id = %s",
            (driver_id,),
        )
        summary = cur.fetchone()
        if not summary:
            return {"error": "Driver not found"}

        # Compute score for this driver
        if summary:
            _compute_scores([summary])

        # Recent trips
        cur.execute(
            """
            SELECT t.id, t.dispatch_entry_no, lo.name AS origin_name, ld.name AS destination_name,
                   t.trip_start,
                   t.ata_in AS trip_end,
                   TIMESTAMPDIFF(MINUTE, t.trip_start, t.ata_in) AS trip_duration_minutes,
                   t.eta_met,
                   t.avg_speed_kmph, t.trip_km, t.trip_status,
                   v.asset_id
            FROM trips t
            LEFT JOIN locations lo ON t.origin_id = lo.id
            LEFT JOIN locations ld ON t.destination_id = ld.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            WHERE t.driver_id = %s
            ORDER BY t.trip_start DESC
            LIMIT 20
            """,
            (driver_id,),
        )
        recent_trips = cur.fetchall()

        # Vehicles used
        cur.execute(
            """
            SELECT DISTINCT v.id, v.asset_id, v.asset_type, COUNT(*) AS trip_count
            FROM trips t
            JOIN vehicles v ON t.vehicle_id = v.id
            WHERE t.driver_id = %s
            GROUP BY v.id, v.asset_id, v.asset_type
            ORDER BY trip_count DESC
            """,
            (driver_id,),
        )
        vehicles_used = cur.fetchall()

        # Frequent routes
        cur.execute(
            """
            SELECT lo.name AS origin, ld.name AS destination, COUNT(*) AS trip_count
            FROM trips t
            JOIN locations lo ON t.origin_id = lo.id
            JOIN locations ld ON t.destination_id = ld.id
            WHERE t.driver_id = %s
            GROUP BY lo.name, ld.name
            ORDER BY trip_count DESC
            LIMIT 10
            """,
            (driver_id,),
        )
        frequent_routes = cur.fetchall()

    for t in recent_trips:
        t["trip_start"] = str(t["trip_start"]) if t["trip_start"] else None
        t["trip_end"] = str(t["trip_end"]) if t["trip_end"] else None

    return {
        "summary": summary,
        "recent_trips": recent_trips,
        "vehicles_used": vehicles_used,
        "frequent_routes": frequent_routes,
    }


@router.get("/{driver_id}/trips")
def get_driver_trips(
    driver_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    conn=Depends(get_db),
):
    offset = (page - 1) * limit

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM trips WHERE driver_id = %s",
            (driver_id,),
        )
        total = cur.fetchone()["cnt"]

        cur.execute(
            """
            SELECT t.id, t.dispatch_entry_no, lo.name AS origin_name, ld.name AS destination_name,
                   t.trip_start,
                   t.ata_in AS trip_end,
                   TIMESTAMPDIFF(MINUTE, t.trip_start, t.ata_in) AS trip_duration_minutes,
                   t.eta_met,
                   t.avg_speed_kmph, t.trip_km, t.trip_status, v.asset_id
            FROM trips t
            LEFT JOIN locations lo ON t.origin_id = lo.id
            LEFT JOIN locations ld ON t.destination_id = ld.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            WHERE t.driver_id = %s
            ORDER BY t.trip_start DESC
            LIMIT %s OFFSET %s
            """,
            (driver_id, limit, offset),
        )
        rows = cur.fetchall()

    for r in rows:
        r["trip_start"] = str(r["trip_start"]) if r["trip_start"] else None
        r["trip_end"] = str(r["trip_end"]) if r["trip_end"] else None

    return {
        "data": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit) if limit else 0,
    }


@router.get("/{driver_id}/trend")
def get_driver_trend(
    driver_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = Query("month", regex="^(month|week|day)$"),
    conn=Depends(get_db),
):
    """Get driver performance trend. Supports date range filtering and grouping by month/week/day."""
    where_parts = ["driver_id = %s", "trip_start IS NOT NULL"]
    params: list = [driver_id]

    if date_from:
        where_parts.append("trip_start >= %s")
        params.append(date_from)
    if date_to:
        where_parts.append("trip_start <= %s")
        params.append(date_to + " 23:59:59")

    where_clause = " AND ".join(where_parts)

    if group_by == "day":
        date_expr = "DATE(trip_start)"
        date_format = "DATE_FORMAT(trip_start, '%%Y-%%m-%%d')"
    elif group_by == "week":
        date_expr = "YEARWEEK(trip_start, 1)"
        date_format = "DATE_FORMAT(MIN(trip_start), '%%Y-W%%v')"
    else:
        date_expr = "DATE_FORMAT(trip_start, '%%Y-%%m')"
        date_format = "DATE_FORMAT(trip_start, '%%Y-%%m')"

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                {date_format} AS period,
                COUNT(*) AS trip_count,
                ROUND(AVG(trip_duration_minutes), 2) AS avg_duration,
                ROUND(SUM(CASE WHEN eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2) AS eta_success_rate,
                ROUND(AVG(avg_speed_kmph), 2) AS avg_speed,
                ROUND(AVG(trip_km), 2) AS avg_distance,
                ROUND(AVG(eta_delay_minutes), 2) AS avg_delay
            FROM trips
            WHERE {where_clause}
            GROUP BY {date_expr}
            ORDER BY {date_expr}
            """,
            params,
        )
        rows = cur.fetchall()
    return rows


@router.get("/{driver_id}/driving-pattern")
def get_driver_driving_pattern(driver_id: int, conn=Depends(get_db)):
    """Get aggregated driving pattern from waypoint data for all vehicles this driver has used."""
    with conn.cursor() as cur:
        # Get hourly speed pattern (aggregated across all waypoints for this driver's vehicles)
        cur.execute(
            """
            SELECT
                HOUR(w.recorded_at) AS hour_of_day,
                ROUND(AVG(w.speed_kmph), 2) AS avg_speed,
                ROUND(MAX(w.speed_kmph), 2) AS max_speed,
                ROUND(MIN(CASE WHEN w.speed_kmph > 0 THEN w.speed_kmph END), 2) AS min_speed,
                COUNT(*) AS data_points,
                ROUND(SUM(CASE WHEN w.speed_kmph = 0 OR w.status LIKE '%%stop%%' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS stop_pct
            FROM waypoints w
            JOIN vehicles v ON w.vehicle_id = v.id
            WHERE v.id IN (SELECT DISTINCT vehicle_id FROM trips WHERE driver_id = %s AND vehicle_id IS NOT NULL)
            GROUP BY HOUR(w.recorded_at)
            ORDER BY hour_of_day
            """,
            (driver_id,),
        )
        hourly_pattern = cur.fetchall()

        # Get speed distribution buckets
        cur.execute(
            """
            SELECT
                CASE
                    WHEN w.speed_kmph = 0 THEN 'Stopped (0)'
                    WHEN w.speed_kmph BETWEEN 1 AND 20 THEN 'Slow (1-20)'
                    WHEN w.speed_kmph BETWEEN 21 AND 40 THEN 'Medium (21-40)'
                    WHEN w.speed_kmph BETWEEN 41 AND 60 THEN 'Fast (41-60)'
                    WHEN w.speed_kmph BETWEEN 61 AND 80 THEN 'Very Fast (61-80)'
                    ELSE 'Over 80'
                END AS speed_range,
                COUNT(*) AS count
            FROM waypoints w
            JOIN vehicles v ON w.vehicle_id = v.id
            WHERE v.id IN (SELECT DISTINCT vehicle_id FROM trips WHERE driver_id = %s AND vehicle_id IS NOT NULL)
              AND w.speed_kmph IS NOT NULL
            GROUP BY speed_range
            ORDER BY FIELD(speed_range, 'Stopped (0)', 'Slow (1-20)', 'Medium (21-40)', 'Fast (41-60)', 'Very Fast (61-80)', 'Over 80')
            """,
            (driver_id,),
        )
        speed_distribution = cur.fetchall()

        # Get daily driving pattern (day of week)
        cur.execute(
            """
            SELECT
                DAYOFWEEK(w.recorded_at) AS day_num,
                DAYNAME(w.recorded_at) AS day_name,
                ROUND(AVG(w.speed_kmph), 2) AS avg_speed,
                COUNT(*) AS data_points
            FROM waypoints w
            JOIN vehicles v ON w.vehicle_id = v.id
            WHERE v.id IN (SELECT DISTINCT vehicle_id FROM trips WHERE driver_id = %s AND vehicle_id IS NOT NULL)
            GROUP BY DAYOFWEEK(w.recorded_at), DAYNAME(w.recorded_at)
            ORDER BY day_num
            """,
            (driver_id,),
        )
        daily_pattern = cur.fetchall()

        # Total waypoint stats
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_points,
                COUNT(DISTINCT DATE(w.recorded_at)) AS total_days,
                ROUND(AVG(w.speed_kmph), 2) AS overall_avg_speed,
                ROUND(MAX(w.speed_kmph), 2) AS top_speed,
                ROUND(SUM(w.distance_from_prev), 2) AS total_distance_tracked
            FROM waypoints w
            JOIN vehicles v ON w.vehicle_id = v.id
            WHERE v.id IN (SELECT DISTINCT vehicle_id FROM trips WHERE driver_id = %s AND vehicle_id IS NOT NULL)
            """,
            (driver_id,),
        )
        stats = cur.fetchone()

    return {
        "hourly_pattern": hourly_pattern,
        "speed_distribution": speed_distribution,
        "daily_pattern": daily_pattern,
        "stats": stats,
    }
