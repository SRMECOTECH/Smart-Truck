from fastapi import APIRouter, Depends, Query
from typing import Optional
from backend.app.core.database import get_db
import math

router = APIRouter(prefix="/trips", tags=["Trips"])


@router.get("")
def list_trips(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    driver_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    trip_status: Optional[str] = None,
    eta_met: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    conn=Depends(get_db),
):
    offset = (page - 1) * limit
    conditions = []
    params = []

    if driver_id:
        conditions.append("t.driver_id = %s")
        params.append(driver_id)
    if vehicle_id:
        conditions.append("t.vehicle_id = %s")
        params.append(vehicle_id)
    if origin:
        conditions.append("lo.name LIKE %s")
        params.append(f"%{origin}%")
    if destination:
        conditions.append("ld.name LIKE %s")
        params.append(f"%{destination}%")
    if trip_status:
        conditions.append("t.trip_status = %s")
        params.append(trip_status)
    if eta_met is not None:
        conditions.append("t.eta_met = %s")
        params.append(1 if eta_met else 0)
    if date_from:
        conditions.append("t.trip_start >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("t.trip_start <= %s")
        params.append(date_to)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*) AS cnt
            FROM trips t
            LEFT JOIN locations lo ON t.origin_id = lo.id
            LEFT JOIN locations ld ON t.destination_id = ld.id
            {where_clause}
            """,
            params,
        )
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT t.id, t.dispatch_entry_no, d.name AS driver_name, v.asset_id,
                   lo.name AS origin_name, ld.name AS destination_name,
                   t.trip_start,
                   t.ata_in AS trip_end,
                   TIMESTAMPDIFF(MINUTE, t.trip_start, t.ata_in) AS trip_duration_minutes,
                   t.eta_met,
                   t.eta_delay_minutes, t.avg_speed_kmph, t.trip_km, t.trip_status,
                   t.is_active, t.material_desc
            FROM trips t
            LEFT JOIN drivers d ON t.driver_id = d.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            LEFT JOIN locations lo ON t.origin_id = lo.id
            LEFT JOIN locations ld ON t.destination_id = ld.id
            {where_clause}
            ORDER BY t.trip_start DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
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


@router.get("/stats")
def get_trip_stats(conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS total_trips,
                SUM(CASE WHEN trip_status = 'C' THEN 1 ELSE 0 END) AS completed_trips,
                SUM(CASE WHEN trip_status != 'C' OR trip_status IS NULL THEN 1 ELSE 0 END) AS active_trips,
                ROUND(AVG(TIMESTAMPDIFF(MINUTE, trip_start, ata_in)), 2) AS avg_duration_minutes,
                ROUND(AVG(avg_speed_kmph), 2) AS avg_speed_kmph,
                ROUND(SUM(CASE WHEN eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2) AS eta_success_rate
            FROM trips
            WHERE trip_start IS NOT NULL AND ata_in IS NOT NULL
        """)
        row = cur.fetchone()
    return row


@router.get("/{trip_id}")
def get_trip_detail(trip_id: int, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.*, 
                   t.ata_in AS trip_end_actual,
                   TIMESTAMPDIFF(MINUTE, t.trip_start, t.ata_in) AS trip_duration_minutes_actual,
                   d.name AS driver_name, d.mobile1 AS driver_mobile,
                   v.asset_id, v.asset_type,
                   lo.name AS origin_name, ld.name AS destination_name,
                   c.cne_name AS customer_name
            FROM trips t
            LEFT JOIN drivers d ON t.driver_id = d.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            LEFT JOIN locations lo ON t.origin_id = lo.id
            LEFT JOIN locations ld ON t.destination_id = ld.id
            LEFT JOIN customers c ON t.customer_id = c.id
            WHERE t.id = %s
            """,
            (trip_id,),
        )
        trip = cur.fetchone()
        if not trip:
            return {"error": "Trip not found"}

        # Get waypoints if any
        cur.execute(
            """
            SELECT latitude, longitude, speed_kmph, status, location_text,
                   distance_from_prev, recorded_at
            FROM waypoints
            WHERE trip_id = %s
            ORDER BY recorded_at
            """,
            (trip_id,),
        )
        waypoints = cur.fetchall()

    # Convert datetimes to strings
    for key in trip:
        if hasattr(trip[key], "isoformat"):
            trip[key] = str(trip[key])

    for w in waypoints:
        w["recorded_at"] = str(w["recorded_at"]) if w["recorded_at"] else None

    return {"trip": trip, "waypoints": waypoints}