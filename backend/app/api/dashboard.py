from fastapi import APIRouter, Depends
from typing import List
from backend.app.core.database import get_db
from backend.app.schemas.dashboard import FleetSummary, DailyTrend, AlertOut

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=FleetSummary)
def get_fleet_summary(conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS total_trips,
                COUNT(DISTINCT driver_id) AS total_drivers,
                COUNT(DISTINCT vehicle_id) AS total_vehicles,
                ROUND(SUM(trip_km), 2) AS total_distance_km,
                ROUND(AVG(avg_speed_kmph), 2) AS avg_speed_kmph,
                ROUND(SUM(CASE WHEN eta_met = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2) AS eta_success_rate
            FROM trips
        """)
        row = cur.fetchone()
    return FleetSummary(**row)


@router.get("/daily-trend", response_model=List[DailyTrend])
def get_daily_trend(days: int = 30, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT stat_date, total_trips, total_distance_km, avg_speed,
                   eta_success_rate, active_drivers, active_vehicles
            FROM daily_fleet_stats
            ORDER BY stat_date DESC
            LIMIT %s
            """,
            (days,),
        )
        rows = cur.fetchall()
    return [DailyTrend(**r) for r in reversed(rows)]


@router.get("/top-drivers")
def get_top_drivers(limit: int = 10, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT driver_id, driver_name, driver_mobile, total_trips,
                   eta_success_rate, avg_speed_kmph, total_distance_km
            FROM driver_summary
            WHERE total_trips >= 5
            ORDER BY total_trips DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return rows


@router.get("/route-heatmap")
def get_route_heatmap(limit: int = 20, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT origin, destination, route_name, trip_count,
                   avg_duration_min, eta_success_rate, avg_distance_km
            FROM route_summary
            ORDER BY trip_count DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return rows


@router.get("/alerts/recent", response_model=List[AlertOut])
def get_recent_alerts(limit: int = 20, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, alert_type, severity, title, message, trip_id,
                   driver_id, vehicle_id, is_acknowledged, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    results = []
    for r in rows:
        r["created_at"] = str(r["created_at"]) if r["created_at"] else None
        r["is_acknowledged"] = bool(r["is_acknowledged"])
        results.append(AlertOut(**r))
    return results
