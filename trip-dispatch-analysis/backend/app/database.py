"""
Enhanced Database Query Functions
Includes pagination, filtering, search, and ETA prediction
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, List
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_i1SF8mhXaWJy@ep-sweet-glade-ai0zyfbt-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
)

_conn = None


def get_conn():
    """Get or create database connection."""
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(DATABASE_URL)
    return _conn


def query(sql, params=None, fetchall=True):
    """Execute a query and return results as list of dicts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            if fetchall:
                return cur.fetchall()
            return cur.fetchone()
    except Exception:
        conn.rollback()
        raise


# ========== HEALTH & SUMMARY ==========

def get_health():
    """Health check."""
    row = query("SELECT COUNT(*) as records FROM trips", fetchall=False)
    return {
        "status": "healthy",
        "records": row["records"],
        "columns": 41
    }


def get_data_summary():
    """Get data summary statistics."""
    row = query("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT driver_id) as total_drivers,
            COUNT(DISTINCT vehicle_id) as total_vehicles,
            MIN(trip_start) as date_start,
            MAX(trip_start) as date_end
        FROM trips
    """, fetchall=False)

    return {
        "total_records": row["total_records"],
        "total_drivers": row["total_drivers"],
        "total_vehicles": row["total_vehicles"],
        "date_range": {
            "start": row["date_start"].isoformat() if row["date_start"] else None,
            "end": row["date_end"].isoformat() if row["date_end"] else None,
        },
        "source_files": ["database"]
    }


# ========== DRIVER FUNCTIONS ==========

def get_all_drivers(page: int = 1, limit: int = 50, search: Optional[str] = None):
    """Get paginated list of drivers with search."""
    offset = (page - 1) * limit

    where_clause = ""
    params = []

    if search:
        where_clause = "WHERE LOWER(driver_name) LIKE %s OR LOWER(driver_mobile) LIKE %s"
        search_pattern = f"%{search.lower()}%"
        params = [search_pattern, search_pattern]

    # Get total count
    count_sql = f"SELECT COUNT(*) as total FROM mv_driver_summary {where_clause}"
    total_row = query(count_sql, params, fetchall=False)
    total = total_row["total"]

    # Get paginated data
    data_sql = f"""
        SELECT
            driver_name as name,
            COALESCE(driver_mobile, '') as mobile,
            total_trips as trip_count,
            eta_success_rate,
            avg_speed_kmph,
            total_distance_km
        FROM mv_driver_summary
        {where_clause}
        ORDER BY total_trips DESC
        LIMIT %s OFFSET %s
    """

    params.extend([limit, offset])
    rows = query(data_sql, params)

    result = []
    for r in rows:
        result.append({
            "name": r["name"],
            "mobile": r["mobile"] or "",
            "trip_count": r["trip_count"],
            "eta_success_rate": float(r["eta_success_rate"]) if r["eta_success_rate"] else 0,
            "avg_speed_kmph": float(r["avg_speed_kmph"]) if r["avg_speed_kmph"] else None,
            "total_distance_km": float(r["total_distance_km"]) if r["total_distance_km"] else None,
            "search_text": f"{r['name']} {r['mobile'] or ''}".lower()
        })

    return {
        "data": result,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit
    }


def get_driver_summary(driver_name: str):
    """Get comprehensive summary for a specific driver."""
    stats = query("""
        SELECT * FROM mv_driver_summary WHERE driver_name = %s
    """, (driver_name.strip(),), fetchall=False)

    if not stats:
        return {"error": "Driver not found", "total_trips": 0}

    driver_id = stats["driver_id"]

    # Get car list
    cars = query("""
        SELECT DISTINCT v.asset_id
        FROM trips t
        JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.driver_id = %s
        ORDER BY v.asset_id
    """, (driver_id,))
    car_list = [c["asset_id"] for c in cars]

    # Get most frequent route
    route_row = query("""
        SELECT lo.name || ' → ' || ld.name as route, COUNT(*) as cnt
        FROM trips t
        JOIN locations lo ON t.origin_id = lo.id
        JOIN locations ld ON t.destination_id = ld.id
        WHERE t.driver_id = %s
        GROUP BY lo.name, ld.name
        ORDER BY cnt DESC
        LIMIT 1
    """, (driver_id,), fetchall=False)
    most_frequent_route = route_row["route"] if route_row else None

    # Get peak operating hour
    peak_row = query("""
        SELECT EXTRACT(HOUR FROM trip_start)::int as hr, COUNT(*) as cnt
        FROM trips
        WHERE driver_id = %s AND trip_start IS NOT NULL
        GROUP BY hr
        ORDER BY cnt DESC
        LIMIT 1
    """, (driver_id,), fetchall=False)
    peak_hour = peak_row["hr"] if peak_row else None

    # Get recent trips
    recent = query("""
        SELECT
            t.dispatch_entry_no as trip_id,
            t.trip_start,
            lo.name || ' → ' || ld.name as route,
            t.trip_duration_minutes,
            t.eta_met,
            t.trip_km,
            v.asset_id as vehicle
        FROM trips t
        LEFT JOIN locations lo ON t.origin_id = lo.id
        LEFT JOIN locations ld ON t.destination_id = ld.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.driver_id = %s AND t.trip_start IS NOT NULL
        ORDER BY t.trip_start DESC
        LIMIT 5
    """, (driver_id,))

    recent_trips = []
    for r in recent:
        duration_hours = round(r["trip_duration_minutes"] / 60, 2) if r["trip_duration_minutes"] else None
        recent_trips.append({
            "trip_id": r["trip_id"] or "N/A",
            "date": r["trip_start"].strftime("%Y-%m-%d") if r["trip_start"] else "N/A",
            "route": r["route"] or "N/A",
            "duration_hours": duration_hours,
            "trip_km": float(r["trip_km"]) if r["trip_km"] else None,
            "vehicle": r["vehicle"],
            "eta_met": bool(r["eta_met"]) if r["eta_met"] is not None else False
        })

    eta_met_count = int(stats["eta_met_count"]) if stats["eta_met_count"] else 0
    total_trips = int(stats["total_trips"])

    return {
        "driver_name": driver_name,
        "driver_mobile": stats["driver_mobile"] or "",
        "total_trips": total_trips,
        "eta_met": eta_met_count,
        "eta_missed": total_trips - eta_met_count,
        "eta_success_rate": float(stats["eta_success_rate"]) if stats["eta_success_rate"] else 0,
        "avg_trip_duration_min": float(stats["avg_duration_min"]) if stats["avg_duration_min"] else None,
        "max_trip_duration_min": float(stats["max_duration_min"]) if stats["max_duration_min"] else None,
        "min_trip_duration_min": float(stats["min_duration_min"]) if stats["min_duration_min"] else None,
        "avg_speed_kmph": float(stats["avg_speed_kmph"]) if stats["avg_speed_kmph"] else None,
        "cars_used": int(stats["vehicles_used"]),
        "car_list": car_list,
        "most_frequent_route": most_frequent_route,
        "total_distance_km": float(stats["total_distance_km"]) if stats["total_distance_km"] else None,
        "avg_distance_km": float(stats["avg_distance_km"]) if stats["avg_distance_km"] else None,
        "peak_operating_hour": peak_hour,
        "recent_trips": recent_trips,
        "avg_eta_delay_min": float(stats["avg_eta_delay_min"]) if stats["avg_eta_delay_min"] else None
    }


def get_driver_trips(driver_name: str, page: int = 1, limit: int = 20):
    """Get paginated trips for a specific driver."""
    # Get driver_id
    driver_row = query("SELECT id FROM drivers WHERE name = %s", (driver_name.strip(),), fetchall=False)
    if not driver_row:
        return {"data": [], "total": 0, "page": page, "limit": limit, "pages": 0}

    driver_id = driver_row["id"]
    offset = (page - 1) * limit

    # Get total count
    count_sql = "SELECT COUNT(*) as total FROM trips WHERE driver_id = %s"
    total_row = query(count_sql, (driver_id,), fetchall=False)
    total = total_row["total"]

    # Get paginated trips
    trips = query("""
        SELECT
            t.dispatch_entry_no,
            t.trip_start,
            t.trip_end,
            lo.name as origin,
            ld.name as destination,
            t.trip_km,
            t.trip_duration_minutes,
            t.eta_met,
            t.trip_status,
            v.asset_id as vehicle
        FROM trips t
        LEFT JOIN locations lo ON t.origin_id = lo.id
        LEFT JOIN locations ld ON t.destination_id = ld.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.driver_id = %s
        ORDER BY t.trip_start DESC NULLS LAST
        LIMIT %s OFFSET %s
    """, (driver_id, limit, offset))

    data = []
    for t in trips:
        data.append({
            "trip_id": t["dispatch_entry_no"],
            "trip_start": t["trip_start"].isoformat() if t["trip_start"] else None,
            "trip_end": t["trip_end"].isoformat() if t["trip_end"] else None,
            "origin": t["origin"],
            "destination": t["destination"],
            "route": f"{t['origin']} → {t['destination']}" if t['origin'] and t['destination'] else None,
            "trip_km": float(t["trip_km"]) if t["trip_km"] else None,
            "duration_minutes": float(t["trip_duration_minutes"]) if t["trip_duration_minutes"] else None,
            "eta_met": bool(t["eta_met"]) if t["eta_met"] is not None else None,
            "status": t["trip_status"],
            "vehicle": t["vehicle"]
        })

    return {
        "data": data,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit
    }


def get_driver_vehicles(driver_name: str):
    """Get all vehicles used by a specific driver."""
    driver_row = query("SELECT id FROM drivers WHERE name = %s", (driver_name.strip(),), fetchall=False)
    if not driver_row:
        return []

    driver_id = driver_row["id"]

    vehicles = query("""
        SELECT
            v.asset_id,
            v.asset_type,
            COUNT(*) as trip_count,
            SUM(t.trip_km) as total_km,
            AVG(t.avg_speed_kmph) as avg_speed
        FROM trips t
        JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.driver_id = %s
        GROUP BY v.asset_id, v.asset_type
        ORDER BY trip_count DESC
    """, (driver_id,))

    result = []
    for v in vehicles:
        result.append({
            "asset_id": v["asset_id"],
            "asset_type": v["asset_type"],
            "trip_count": v["trip_count"],
            "total_km": float(v["total_km"]) if v["total_km"] else 0,
            "avg_speed": float(v["avg_speed"]) if v["avg_speed"] else None
        })

    return result


# ========== TRIP FUNCTIONS ==========

def get_trips_paginated(
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        driver_name: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
):
    """Get paginated trips with filtering."""
    offset = (page - 1) * limit

    where_clauses = []
    params = []

    if search:
        where_clauses.append("(t.dispatch_entry_no ILIKE %s OR lo.name ILIKE %s OR ld.name ILIKE %s)")
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    if driver_name:
        where_clauses.append("d.name = %s")
        params.append(driver_name)

    if vehicle_id:
        where_clauses.append("v.asset_id = %s")
        params.append(vehicle_id)

    if status:
        where_clauses.append("t.trip_status = %s")
        params.append(status)

    if start_date:
        where_clauses.append("t.trip_start >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("t.trip_start <= %s")
        params.append(end_date)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get total count
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM trips t
        LEFT JOIN drivers d ON t.driver_id = d.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        LEFT JOIN locations lo ON t.origin_id = lo.id
        LEFT JOIN locations ld ON t.destination_id = ld.id
        {where_sql}
    """
    total_row = query(count_sql, params, fetchall=False)
    total = total_row["total"]

    # Get paginated data
    data_sql = f"""
        SELECT
            t.dispatch_entry_no,
            t.trip_start,
            t.trip_end,
            lo.name as origin,
            ld.name as destination,
            t.trip_km,
            t.trip_duration_minutes,
            t.eta_met,
            t.trip_status,
            d.name as driver_name,
            v.asset_id as vehicle_id
        FROM trips t
        LEFT JOIN drivers d ON t.driver_id = d.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        LEFT JOIN locations lo ON t.origin_id = lo.id
        LEFT JOIN locations ld ON t.destination_id = ld.id
        {where_sql}
        ORDER BY t.trip_start DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    rows = query(data_sql, params)

    data = []
    for r in rows:
        data.append({
            "trip_id": r["dispatch_entry_no"],
            "trip_start": r["trip_start"].isoformat() if r["trip_start"] else None,
            "trip_end": r["trip_end"].isoformat() if r["trip_end"] else None,
            "origin": r["origin"],
            "destination": r["destination"],
            "route": f"{r['origin']} → {r['destination']}" if r['origin'] and r['destination'] else None,
            "trip_km": float(r["trip_km"]) if r["trip_km"] else None,
            "duration_minutes": float(r["trip_duration_minutes"]) if r["trip_duration_minutes"] else None,
            "eta_met": bool(r["eta_met"]) if r["eta_met"] is not None else None,
            "status": r["trip_status"],
            "driver_name": r["driver_name"],
            "vehicle_id": r["vehicle_id"]
        })

    return {
        "data": data,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit
    }


def get_trip_details(trip_id: str):
    """Get detailed information for a specific trip."""
    trip = query("""
        SELECT
            t.*,
            d.name as driver_name,
            d.mobile1 as driver_mobile,
            v.asset_id,
            v.asset_type,
            lo.name as origin,
            ld.name as destination
        FROM trips t
        LEFT JOIN drivers d ON t.driver_id = d.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        LEFT JOIN locations lo ON t.origin_id = lo.id
        LEFT JOIN locations ld ON t.destination_id = ld.id
        WHERE t.dispatch_entry_no = %s
    """, (trip_id,), fetchall=False)

    if not trip:
        return None

    return {
        "trip_id": trip["dispatch_entry_no"],
        "driver_name": trip["driver_name"],
        "driver_mobile": trip["driver_mobile"],
        "vehicle_id": trip["asset_id"],
        "vehicle_type": trip["asset_type"],
        "origin": trip["origin"],
        "destination": trip["destination"],
        "route": f"{trip['origin']} → {trip['destination']}" if trip['origin'] and trip['destination'] else None,
        "trip_start": trip["trip_start"].isoformat() if trip["trip_start"] else None,
        "trip_end": trip["trip_end"].isoformat() if trip["trip_end"] else None,
        "trip_eta": trip["trip_eta"].isoformat() if trip["trip_eta"] else None,
        "trip_km": float(trip["trip_km"]) if trip["trip_km"] else None,
        "duration_minutes": float(trip["trip_duration_minutes"]) if trip["trip_duration_minutes"] else None,
        "avg_speed_kmph": float(trip["avg_speed_kmph"]) if trip["avg_speed_kmph"] else None,
        "eta_met": bool(trip["eta_met"]) if trip["eta_met"] is not None else None,
        "eta_delay_minutes": float(trip["eta_delay_minutes"]) if trip["eta_delay_minutes"] else None,
        "status": trip["trip_status"],
        "material_desc": trip["material_desc"],
        "invoice_no": trip["invoice_no"]
    }


# ========== NEW: VALIDATION FUNCTION ==========

def get_trip_for_validation(trip_id: int) -> Optional[Dict]:
    """
    Fetch a completed trip by dispatch_entry_no for ML prediction validation.

    Parameters:
        trip_id: The dispatch_entry_no (trip ID)

    Returns:
        Dict with trip details or None if not found
    """
    trip = query("""
        SELECT
            t.dispatch_entry_no,
            t.trip_start,
            t.ata_in,
            t.trip_duration_minutes,
            t.trip_km,
            t.avg_speed_kmph,
            t.eta_met,
            t.eta_delay_minutes,
            t.driver_id,
            d.name as driver_name,
            lo.name AS origin,
            ld.name AS destination,
            v.asset_type,
            v.vehicle_no
        FROM trips t
        JOIN locations lo ON t.origin_id = lo.id
        JOIN locations ld ON t.destination_id = ld.id
        LEFT JOIN drivers d ON t.driver_id = d.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.dispatch_entry_no = %s
          AND t.trip_start IS NOT NULL
          AND t.ata_in IS NOT NULL
          AND t.trip_status = 'C'
    """, (trip_id,), fetchall=False)

    return dict(trip) if trip else None


# ========== VEHICLE FUNCTIONS ==========

def get_vehicles_paginated(page: int = 1, limit: int = 50, search: Optional[str] = None):
    """Get paginated list of vehicles with search."""
    offset = (page - 1) * limit

    where_clause = ""
    params = []

    if search:
        where_clause = "WHERE v.asset_id ILIKE %s OR v.asset_type ILIKE %s"
        search_pattern = f"%{search}%"
        params = [search_pattern, search_pattern]

    # Get total count
    count_sql = f"SELECT COUNT(*) as total FROM vehicles v {where_clause}"
    total_row = query(count_sql, params, fetchall=False)
    total = total_row["total"]

    # Get paginated data with stats
    data_sql = f"""
        SELECT
            v.asset_id,
            v.asset_type,
            COUNT(t.id) as trip_count,
            COUNT(DISTINCT t.driver_id) as driver_count,
            SUM(t.trip_km) as total_km
        FROM vehicles v
        LEFT JOIN trips t ON v.id = t.vehicle_id
        {where_clause}
        GROUP BY v.asset_id, v.asset_type
        ORDER BY trip_count DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    rows = query(data_sql, params)

    data = []
    for r in rows:
        data.append({
            "asset_id": r["asset_id"],
            "asset_type": r["asset_type"],
            "trip_count": r["trip_count"],
            "driver_count": r["driver_count"],
            "total_km": float(r["total_km"]) if r["total_km"] else 0
        })

    return {
        "data": data,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit
    }


def get_vehicle_trips(vehicle_id: str, page: int = 1, limit: int = 20):
    """Get paginated trips for a specific vehicle."""
    # Get vehicle DB id
    vehicle_row = query("SELECT id FROM vehicles WHERE asset_id = %s", (vehicle_id,), fetchall=False)
    if not vehicle_row:
        return {"data": [], "total": 0, "page": page, "limit": limit, "pages": 0}

    vehicle_db_id = vehicle_row["id"]
    offset = (page - 1) * limit

    # Get total count
    count_sql = "SELECT COUNT(*) as total FROM trips WHERE vehicle_id = %s"
    total_row = query(count_sql, (vehicle_db_id,), fetchall=False)
    total = total_row["total"]

    # Get paginated trips
    trips = query("""
        SELECT
            t.dispatch_entry_no,
            t.trip_start,
            t.trip_end,
            lo.name as origin,
            ld.name as destination,
            t.trip_km,
            t.trip_duration_minutes,
            t.eta_met,
            d.name as driver_name
        FROM trips t
        LEFT JOIN locations lo ON t.origin_id = lo.id
        LEFT JOIN locations ld ON t.destination_id = ld.id
        LEFT JOIN drivers d ON t.driver_id = d.id
        WHERE t.vehicle_id = %s
        ORDER BY t.trip_start DESC NULLS LAST
        LIMIT %s OFFSET %s
    """, (vehicle_db_id, limit, offset))

    data = []
    for t in trips:
        data.append({
            "trip_id": t["dispatch_entry_no"],
            "trip_start": t["trip_start"].isoformat() if t["trip_start"] else None,
            "trip_end": t["trip_end"].isoformat() if t["trip_end"] else None,
            "origin": t["origin"],
            "destination": t["destination"],
            "route": f"{t['origin']} → {t['destination']}" if t['origin'] and t['destination'] else None,
            "trip_km": float(t["trip_km"]) if t["trip_km"] else None,
            "duration_minutes": float(t["trip_duration_minutes"]) if t["trip_duration_minutes"] else None,
            "eta_met": bool(t["eta_met"]) if t["eta_met"] is not None else None,
            "driver_name": t["driver_name"]
        })

    return {
        "data": data,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit
    }


# ========== ANALYTICS FUNCTIONS ==========

def get_trip_overview():
    """Get overall trip statistics."""
    stats = query("""
        SELECT
            COUNT(*) as total_trips,
            SUM(CASE WHEN eta_met THEN 1 ELSE 0 END) as eta_met,
            ROUND(SUM(CASE WHEN eta_met THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as eta_success_rate,
            ROUND(SUM(trip_km), 2) as total_distance_km,
            COUNT(DISTINCT driver_id) as active_drivers,
            COUNT(DISTINCT vehicle_id) as active_vehicles,
            ROUND(AVG(trip_duration_minutes), 2) as avg_trip_duration_min
        FROM trips
    """, fetchall=False)

    # Top routes
    top_routes_rows = query("""
        SELECT route, trip_count as count
        FROM mv_route_summary
        ORDER BY trip_count DESC
        LIMIT 10
    """)

    total_trips = int(stats["total_trips"])
    eta_met = int(stats["eta_met"]) if stats["eta_met"] else 0

    return {
        "total_trips": total_trips,
        "eta_met": eta_met,
        "eta_missed": total_trips - eta_met,
        "eta_success_rate": float(stats["eta_success_rate"]) if stats["eta_success_rate"] else 0,
        "total_distance_km": float(stats["total_distance_km"]) if stats["total_distance_km"] else None,
        "active_drivers": int(stats["active_drivers"]),
        "active_vehicles": int(stats["active_vehicles"]),
        "avg_trip_duration_min": float(stats["avg_trip_duration_min"]) if stats["avg_trip_duration_min"] else None,
        "top_routes": [{"route": r["route"], "count": int(r["count"])} for r in top_routes_rows]
    }


def get_route_analysis(limit: int = 20):
    """Analyze routes and their performance."""
    rows = query("""
        SELECT
            route,
            trip_count,
            avg_duration_min,
            eta_success_rate,
            avg_distance_km
        FROM mv_route_summary
        ORDER BY trip_count DESC
        LIMIT %s
    """, (limit,))

    return [
        {
            "route": r["route"],
            "trip_count": int(r["trip_count"]),
            "avg_duration_min": float(r["avg_duration_min"]) if r["avg_duration_min"] else None,
            "eta_success_rate": float(r["eta_success_rate"]) if r["eta_success_rate"] else 0,
            "avg_distance_km": float(r["avg_distance_km"]) if r["avg_distance_km"] else None
        }
        for r in rows
    ]


def get_driver_performance_comparison(limit: int = 10):
    """Get top performing drivers."""
    rows = query("""
        SELECT
            driver_name,
            total_trips,
            eta_success_rate,
            eta_met_count as eta_met
        FROM mv_driver_summary
        WHERE total_trips >= 5
        ORDER BY eta_success_rate DESC
        LIMIT %s
    """, (limit,))

    return [
        {
            "driver_name": r["driver_name"],
            "total_trips": int(r["total_trips"]),
            "eta_success_rate": float(r["eta_success_rate"]) if r["eta_success_rate"] else 0,
            "eta_met": int(r["eta_met"]) if r["eta_met"] else 0
        }
        for r in rows
    ]


def predict_eta(origin: str, destination: str, driver_name: Optional[str] = None, vehicle_id: Optional[str] = None):
    """Predict ETA based on historical data."""
    where_clauses = ["lo.name = %s", "ld.name = %s"]
    params = [origin, destination]

    if driver_name:
        where_clauses.append("d.name = %s")
        params.append(driver_name)

    if vehicle_id:
        where_clauses.append("v.asset_id = %s")
        params.append(vehicle_id)

    where_sql = " AND ".join(where_clauses)

    # Get statistics for this route
    stats = query(f"""
        SELECT
            COUNT(*) as sample_size,
            AVG(t.trip_duration_minutes) as avg_duration,
            MIN(t.trip_duration_minutes) as min_duration,
            MAX(t.trip_duration_minutes) as max_duration,
            AVG(t.trip_km) as avg_distance,
            AVG(t.avg_speed_kmph) as avg_speed
        FROM trips t
        LEFT JOIN locations lo ON t.origin_id = lo.id
        LEFT JOIN locations ld ON t.destination_id = ld.id
        LEFT JOIN drivers d ON t.driver_id = d.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        WHERE {where_sql}
        AND t.trip_duration_minutes IS NOT NULL
    """, params, fetchall=False)

    if not stats or stats["sample_size"] == 0:
        return {
            "prediction_available": False,
            "message": "Insufficient historical data for this route",
            "sample_size": 0
        }

    return {
        "prediction_available": True,
        "origin": origin,
        "destination": destination,
        "predicted_duration_minutes": round(float(stats["avg_duration"]), 2) if stats["avg_duration"] else None,
        "predicted_duration_hours": round(float(stats["avg_duration"]) / 60, 2) if stats["avg_duration"] else None,
        "min_duration_minutes": round(float(stats["min_duration"]), 2) if stats["min_duration"] else None,
        "max_duration_minutes": round(float(stats["max_duration"]), 2) if stats["max_duration"] else None,
        "avg_distance_km": round(float(stats["avg_distance"]), 2) if stats["avg_distance"] else None,
        "avg_speed_kmph": round(float(stats["avg_speed"]), 2) if stats["avg_speed"] else None,
        "sample_size": int(stats["sample_size"]),
        "confidence": "high" if stats["sample_size"] >= 10 else "medium" if stats["sample_size"] >= 5 else "low"
    }


def get_route_stats(origin: str, destination: str):
    """Get detailed statistics for a specific route."""
    stats = query("""
        SELECT
            COUNT(*) as total_trips,
            AVG(t.trip_duration_minutes) as avg_duration,
            AVG(t.trip_km) as avg_distance,
            SUM(CASE WHEN t.eta_met THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) * 100 as eta_success_rate,
            COUNT(DISTINCT t.driver_id) as unique_drivers,
            COUNT(DISTINCT t.vehicle_id) as unique_vehicles
        FROM trips t
        JOIN locations lo ON t.origin_id = lo.id
        JOIN locations ld ON t.destination_id = ld.id
        WHERE lo.name = %s AND ld.name = %s
    """, (origin, destination), fetchall=False)

    if not stats or stats["total_trips"] == 0:
        return {
            "route": f"{origin} → {destination}",
            "data_available": False
        }

    return {
        "route": f"{origin} → {destination}",
        "data_available": True,
        "total_trips": int(stats["total_trips"]),
        "avg_duration_minutes": round(float(stats["avg_duration"]), 2) if stats["avg_duration"] else None,
        "avg_distance_km": round(float(stats["avg_distance"]), 2) if stats["avg_distance"] else None,
        "eta_success_rate": round(float(stats["eta_success_rate"]), 2) if stats["eta_success_rate"] else 0,
        "unique_drivers": int(stats["unique_drivers"]),
        "unique_vehicles": int(stats["unique_vehicles"])
    }


# ========== LOOKUP ENDPOINTS ==========

def get_all_locations():
    """Get all location names for dropdowns."""
    rows = query("SELECT name FROM locations ORDER BY name")
    return [r["name"] for r in rows]


def get_all_driver_names():
    """Get all driver names for dropdowns."""
    rows = query("SELECT name FROM drivers ORDER BY name")
    return [r["name"] for r in rows]