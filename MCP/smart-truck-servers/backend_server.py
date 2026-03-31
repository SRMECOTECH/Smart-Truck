from fastmcp import FastMCP
import httpx
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

mcp = FastMCP("SmartTruckBackend")


async def _get(path: str, params: dict | None = None) -> dict | list:
    """Helper: GET request to backend API."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BACKEND_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


# ── Dashboard ────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_fleet_summary() -> dict:
    """Get fleet-wide summary: total trips, drivers, vehicles, distance, avg speed, ETA success rate."""
    return await _get("/dashboard/summary")


@mcp.tool()
async def get_daily_trend(days: int = 30) -> dict:
    """Get daily trip trend data for the last N days."""
    return await _get("/dashboard/daily-trend", {"days": days})


@mcp.tool()
async def get_top_drivers(limit: int = 10) -> dict:
    """Get top drivers ranked by ETA success rate."""
    return await _get("/dashboard/top-drivers", {"limit": limit})


@mcp.tool()
async def get_route_heatmap(limit: int = 20) -> dict:
    """Get route frequency heatmap showing the busiest origin-destination pairs."""
    return await _get("/dashboard/route-heatmap", {"limit": limit})


@mcp.tool()
async def get_recent_alerts(limit: int = 20) -> dict:
    """Get recent fleet alerts (anomalies, delays, issues)."""
    return await _get("/dashboard/alerts/recent", {"limit": limit})


# ── Drivers ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_drivers(page: int = 1, limit: int = 20, search: str = "", sort_by: str = "total_trips", sort_order: str = "desc") -> dict:
    """List drivers with pagination. Search by name. Sort by total_trips, eta_success_rate, avg_speed_kmh."""
    params = {"page": page, "limit": limit, "sort_by": sort_by, "sort_order": sort_order}
    if search:
        params["search"] = search
    return await _get("/drivers", params)


@mcp.tool()
async def get_driver_detail(driver_id: int) -> dict:
    """Get detailed driver profile: summary stats, recent trips, vehicles used, frequent routes."""
    return await _get(f"/drivers/{driver_id}")


@mcp.tool()
async def get_driver_trips(driver_id: int, page: int = 1, limit: int = 20) -> dict:
    """Get paginated trips for a specific driver."""
    return await _get(f"/drivers/{driver_id}/trips", {"page": page, "limit": limit})


@mcp.tool()
async def get_driver_trend(driver_id: int, group_by: str = "month", date_from: str = "", date_to: str = "") -> dict:
    """Get driver performance trend over time. group_by: month, week, or day."""
    params = {"group_by": group_by}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    return await _get(f"/drivers/{driver_id}/trend", params)


@mcp.tool()
async def get_driver_driving_pattern(driver_id: int) -> dict:
    """Get driver waypoint-based driving patterns: hourly activity, speed distribution, daily patterns."""
    return await _get(f"/drivers/{driver_id}/driving-pattern")


# ── Vehicles ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_vehicles(page: int = 1, limit: int = 20, search: str = "", sort_by: str = "total_trips", sort_order: str = "desc") -> dict:
    """List vehicles with pagination. Search by asset ID. Sort by total_trips, total_distance_km."""
    params = {"page": page, "limit": limit, "sort_by": sort_by, "sort_order": sort_order}
    if search:
        params["search"] = search
    return await _get("/vehicles", params)


@mcp.tool()
async def get_vehicle_detail(vehicle_id: int) -> dict:
    """Get vehicle details: summary stats, drivers who used it, recent trips."""
    return await _get(f"/vehicles/{vehicle_id}")


@mcp.tool()
async def get_vehicle_trips(vehicle_id: int, page: int = 1, limit: int = 20) -> dict:
    """Get paginated trips for a specific vehicle."""
    return await _get(f"/vehicles/{vehicle_id}/trips", {"page": page, "limit": limit})


# ── Trips ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_trips(
    page: int = 1, limit: int = 20,
    driver_id: int = 0, vehicle_id: int = 0,
    origin: str = "", destination: str = "",
    trip_status: str = "", eta_met: str = "",
    date_from: str = "", date_to: str = ""
) -> dict:
    """List trips with filters. Filter by driver_id, vehicle_id, origin, destination, trip_status, eta_met (yes/no), date range."""
    params = {"page": page, "limit": limit}
    if driver_id:
        params["driver_id"] = driver_id
    if vehicle_id:
        params["vehicle_id"] = vehicle_id
    if origin:
        params["origin"] = origin
    if destination:
        params["destination"] = destination
    if trip_status:
        params["trip_status"] = trip_status
    if eta_met:
        params["eta_met"] = eta_met
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    return await _get("/trips", params)


@mcp.tool()
async def get_trip_stats() -> dict:
    """Get trip statistics: total, completed, active, avg duration, avg speed, ETA success rate."""
    return await _get("/trips/stats")


@mcp.tool()
async def get_trip_detail(trip_id: int) -> dict:
    """Get full trip detail with waypoints, driver info, vehicle info, customer info."""
    return await _get(f"/trips/{trip_id}")


# ── Routes Analysis ──────────────────────────────────────────────────────────

@mcp.tool()
async def list_routes(page: int = 1, limit: int = 20, search: str = "", sort_by: str = "trip_count", sort_order: str = "desc") -> dict:
    """List routes (origin-destination pairs) with stats. Sort by trip_count, avg_duration_hours."""
    params = {"page": page, "limit": limit, "sort_by": sort_by, "sort_order": sort_order}
    if search:
        params["search"] = search
    return await _get("/routes", params)


@mcp.tool()
async def get_route_detail(origin: str, destination: str) -> dict:
    """Get detailed route analysis: time patterns, top drivers, recent trips for a specific origin-destination pair."""
    return await _get("/routes/detail", {"origin": origin, "destination": destination})


# ── Migration / Admin ────────────────────────────────────────────────────────

@mcp.tool()
async def get_migration_status() -> dict:
    """Check database row counts for all tables — useful to verify data is loaded."""
    return await _get("/migrate/status")


@mcp.tool()
async def refresh_summaries() -> dict:
    """Refresh all summary tables (driver, route, vehicle, daily, time patterns). POST request."""
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{BACKEND_URL}/migrate/refresh-summaries")
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8002)
