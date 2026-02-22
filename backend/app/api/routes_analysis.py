from fastapi import APIRouter, Depends, Query
from typing import Optional
from backend.app.core.database import get_db
import math

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get("")
def list_routes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: str = "trip_count",
    sort_order: str = "desc",
    conn=Depends(get_db),
):
    offset = (page - 1) * limit
    allowed_sorts = {"trip_count", "avg_duration_min", "eta_success_rate", "avg_distance_km"}
    if sort_by not in allowed_sorts:
        sort_by = "trip_count"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    where = ""
    params = []
    if search:
        where = "WHERE route_name LIKE %s"
        params = [f"%{search}%"]

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM route_summary {where}", params)
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT id, origin, destination, route_name, trip_count,
                   avg_duration_min, eta_success_rate, avg_distance_km
            FROM route_summary
            {where}
            ORDER BY {sort_by} {sort_order}
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

    return {
        "data": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit) if limit else 0,
    }


@router.get("/detail")
def get_route_detail(origin: str, destination: str, conn=Depends(get_db)):
    with conn.cursor() as cur:
        # Route summary
        cur.execute(
            "SELECT * FROM route_summary WHERE origin = %s AND destination = %s",
            (origin, destination),
        )
        summary = cur.fetchone()

        # Time patterns
        cur.execute(
            """
            SELECT hour_of_day, day_of_week, avg_duration, trip_count, eta_success_rate
            FROM route_time_patterns
            WHERE origin = %s AND destination = %s
            ORDER BY day_of_week, hour_of_day
            """,
            (origin, destination),
        )
        time_patterns = cur.fetchall()

        # Top drivers on this route
        cur.execute(
            """
            SELECT d.id AS driver_id, d.name AS driver_name, COUNT(*) AS trip_count,
                   ROUND(AVG(t.trip_duration_minutes), 2) AS avg_duration,
                   ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2) AS eta_rate
            FROM trips t
            JOIN drivers d ON t.driver_id = d.id
            JOIN locations lo ON t.origin_id = lo.id
            JOIN locations ld ON t.destination_id = ld.id
            WHERE lo.name = %s AND ld.name = %s
            GROUP BY d.id, d.name
            ORDER BY trip_count DESC
            LIMIT 10
            """,
            (origin, destination),
        )
        top_drivers = cur.fetchall()

        # Recent trips on this route
        cur.execute(
            """
            SELECT t.id, t.dispatch_entry_no, d.name AS driver_name, v.asset_id,
                   t.trip_start,
                   t.ata_in AS trip_end,
                   TIMESTAMPDIFF(MINUTE, t.trip_start, t.ata_in) AS trip_duration_minutes,
                   t.eta_met, t.avg_speed_kmph
            FROM trips t
            LEFT JOIN drivers d ON t.driver_id = d.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            JOIN locations lo ON t.origin_id = lo.id
            JOIN locations ld ON t.destination_id = ld.id
            WHERE lo.name = %s AND ld.name = %s
            ORDER BY t.trip_start DESC
            LIMIT 20
            """,
            (origin, destination),
        )
        recent_trips = cur.fetchall()

    for t in recent_trips:
        t["trip_start"] = str(t["trip_start"]) if t["trip_start"] else None

    return {
        "summary": summary,
        "time_patterns": time_patterns,
        "top_drivers": top_drivers,
        "recent_trips": recent_trips,
    }