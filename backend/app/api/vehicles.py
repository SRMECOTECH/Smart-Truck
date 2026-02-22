from fastapi import APIRouter, Depends, Query
from typing import Optional
from backend.app.core.database import get_db
import math

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("")
def list_vehicles(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: str = "total_trips",
    sort_order: str = "desc",
    conn=Depends(get_db),
):
    offset = (page - 1) * limit
    allowed_sorts = {"total_trips", "avg_speed_kmph", "total_distance_km", "eta_success_rate", "asset_id"}
    if sort_by not in allowed_sorts:
        sort_by = "total_trips"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    where = ""
    params = []
    if search:
        where = "WHERE asset_id LIKE %s OR asset_type LIKE %s"
        params = [f"%{search}%", f"%{search}%"]

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM vehicle_summary {where}", params)
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT vehicle_id, asset_id, asset_type, total_trips, drivers_used,
                   avg_speed_kmph, total_distance_km, avg_distance_km, eta_success_rate
            FROM vehicle_summary
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


@router.get("/{vehicle_id}")
def get_vehicle_detail(vehicle_id: int, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM vehicle_summary WHERE vehicle_id = %s",
            (vehicle_id,),
        )
        summary = cur.fetchone()
        if not summary:
            return {"error": "Vehicle not found"}

        # Drivers who drove this vehicle
        cur.execute(
            """
            SELECT d.id AS driver_id, d.name AS driver_name, COUNT(*) AS trip_count
            FROM trips t
            JOIN drivers d ON t.driver_id = d.id
            WHERE t.vehicle_id = %s
            GROUP BY d.id, d.name
            ORDER BY trip_count DESC
            LIMIT 10
            """,
            (vehicle_id,),
        )
        drivers_used = cur.fetchall()

        # Recent trips
        cur.execute(
            """
            SELECT t.id, t.dispatch_entry_no, d.name AS driver_name,
                   lo.name AS origin_name, ld.name AS destination_name,
                   t.trip_start, t.trip_duration_minutes, t.eta_met, t.avg_speed_kmph
            FROM trips t
            LEFT JOIN drivers d ON t.driver_id = d.id
            LEFT JOIN locations lo ON t.origin_id = lo.id
            LEFT JOIN locations ld ON t.destination_id = ld.id
            WHERE t.vehicle_id = %s
            ORDER BY t.trip_start DESC
            LIMIT 20
            """,
            (vehicle_id,),
        )
        recent_trips = cur.fetchall()

    for t in recent_trips:
        t["trip_start"] = str(t["trip_start"]) if t["trip_start"] else None

    return {
        "summary": summary,
        "drivers_used": drivers_used,
        "recent_trips": recent_trips,
    }


@router.get("/{vehicle_id}/trips")
def get_vehicle_trips(
    vehicle_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    conn=Depends(get_db),
):
    offset = (page - 1) * limit

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM trips WHERE vehicle_id = %s",
            (vehicle_id,),
        )
        total = cur.fetchone()["cnt"]

        cur.execute(
            """
            SELECT t.id, t.dispatch_entry_no, d.name AS driver_name,
                   lo.name AS origin_name, ld.name AS destination_name,
                   t.trip_start, t.trip_duration_minutes, t.eta_met,
                   t.avg_speed_kmph, t.trip_km, t.trip_status
            FROM trips t
            LEFT JOIN drivers d ON t.driver_id = d.id
            LEFT JOIN locations lo ON t.origin_id = lo.id
            LEFT JOIN locations ld ON t.destination_id = ld.id
            WHERE t.vehicle_id = %s
            ORDER BY t.trip_start DESC
            LIMIT %s OFFSET %s
            """,
            (vehicle_id, limit, offset),
        )
        rows = cur.fetchall()

    for r in rows:
        r["trip_start"] = str(r["trip_start"]) if r["trip_start"] else None

    return {
        "data": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit) if limit else 0,
    }
