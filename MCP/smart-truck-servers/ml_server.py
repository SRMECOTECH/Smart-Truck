"""
MCP Server wrapping the Smart-Truck ML Service API (port 8001).
Exposes prediction, scoring, forecasting, optimization, and model management tools.
"""

from fastmcp import FastMCP
import httpx
import os

ML_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")

mcp = FastMCP("SmartTruckML")


async def _get(path: str, params: dict | None = None) -> dict | list:
    """Helper: GET request to ML service."""
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"{ML_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def _post(path: str, json_data: dict | None = None) -> dict:
    """Helper: POST request to ML service."""
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{ML_URL}{path}", json=json_data)
        r.raise_for_status()
        return r.json()


# ── ETA Prediction ───────────────────────────────────────────────────────────

@mcp.tool()
async def predict_eta(
    origin: str, destination: str,
    driver_id: int, vehicle_id: int,
    trip_km: float, trip_start: str
) -> dict:
    """Predict trip ETA. Provide origin, destination, driver_id, vehicle_id, trip_km, and trip_start (ISO datetime)."""
    return await _post("/ml/predict/eta", {
        "origin": origin,
        "destination": destination,
        "driver_id": driver_id,
        "vehicle_id": vehicle_id,
        "trip_km": trip_km,
        "trip_start": trip_start,
    })


# ── Anomaly Detection ───────────────────────────────────────────────────────

@mcp.tool()
async def detect_anomaly(
    trip_duration_minutes: float,
    eta_delay_minutes: float,
    speed_kmh: float = 0,
    distance_km: float = 0,
    halt_duration_minutes: float = 0,
    num_halts: int = 0
) -> dict:
    """Detect if a trip is anomalous. Provide trip metrics to check for unusual patterns."""
    return await _post("/ml/predict/anomaly", {
        "trip_duration_minutes": trip_duration_minutes,
        "eta_delay_minutes": eta_delay_minutes,
        "speed_kmh": speed_kmh,
        "distance_km": distance_km,
        "halt_duration_minutes": halt_duration_minutes,
        "num_halts": num_halts,
    })


# ── Driver Scoring ───────────────────────────────────────────────────────────

@mcp.tool()
async def get_driver_scores(limit: int = 100) -> dict:
    """Get all drivers ranked by composite performance score. Returns scores, ETA rates, and rankings."""
    return await _get("/ml/drivers/scores", {"limit": limit})


@mcp.tool()
async def get_single_driver_score(driver_id: int) -> dict:
    """Get the performance score and detailed breakdown for a specific driver."""
    return await _get(f"/ml/drivers/{driver_id}/score")


# ── Demand Forecasting ───────────────────────────────────────────────────────

@mcp.tool()
async def forecast_demand(route: str = "") -> dict:
    """Forecast trip demand for routes. Optionally filter by route in format 'Origin -> Destination'."""
    params = {}
    if route:
        params["route"] = route
    return await _get("/ml/forecast/demand", params)


@mcp.tool()
async def forecast_trips(route: str = "") -> dict:
    """Forecast expected number of trips for the next week. Optionally filter by route."""
    params = {}
    if route:
        params["route"] = route
    return await _get("/ml/forecast/trips", params)


# ── Route Optimization ──────────────────────────────────────────────────────

@mcp.tool()
async def optimize_route(
    origin: str, destination: str,
    trip_km: float, hour: int = 9, day_of_week: int = 1
) -> dict:
    """Find the optimal route between locations. Provide origin, destination, trip_km, hour (0-23), day_of_week (0=Mon)."""
    return await _post("/ml/optimize/route", {
        "origin": origin,
        "destination": destination,
        "trip_km": trip_km,
        "hour": hour,
        "day_of_week": day_of_week,
    })


@mcp.tool()
async def get_hub_locations() -> dict:
    """Get hub location analysis — identifies key logistics hubs from trip data."""
    return await _get("/ml/optimize/hubs")


# ── Driver Recommendation ───────────────────────────────────────────────────

@mcp.tool()
async def recommend_drivers(origin: str, destination: str, top_n: int = 5) -> dict:
    """Recommend the best drivers for a specific route based on historical performance."""
    return await _post("/ml/recommend/drivers", {
        "origin": origin,
        "destination": destination,
        "top_n": top_n,
    })


# ── Model Management ────────────────────────────────────────────────────────

@mcp.tool()
async def list_ml_models() -> dict:
    """List all trained ML models with their versions, status, and performance metrics."""
    return await _get("/ml/models")


@mcp.tool()
async def compare_ml_models() -> dict:
    """Compare all active ML models side by side — metrics, accuracy, training dates."""
    return await _get("/ml/models/comparison")


@mcp.tool()
async def get_model_details(model_name: str) -> dict:
    """Get detailed info about a specific ML model. Names: eta_predictor, anomaly_detector, driver_scorer, demand_forecaster, route_optimizer, driver_recommender."""
    return await _get(f"/ml/models/{model_name}")


# ── Training ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def train_model(model_name: str) -> dict:
    """Trigger training for a specific ML model (runs in background). Names: eta_predictor, anomaly_detector, driver_scorer, demand_forecaster, route_optimizer, driver_recommender."""
    return await _post(f"/ml/train/{model_name}")


@mcp.tool()
async def train_all_models() -> dict:
    """Trigger training for ALL 6 ML models in background."""
    return await _post("/ml/train-all")


@mcp.tool()
async def check_training_readiness() -> dict:
    """Check if the database has enough data to train models. Returns readiness per model."""
    return await _get("/ml/training/readiness")


@mcp.tool()
async def clear_model_cache(model_name: str = "") -> dict:
    """Clear ML model cache. Optionally specify model_name, otherwise clears all."""
    params = {}
    if model_name:
        params["model"] = model_name
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{ML_URL}/ml/cache/clear", params=params)
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8003)
