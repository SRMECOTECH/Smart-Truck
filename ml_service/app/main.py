"""
Smart-Truck ML Service API
Serves predictions from all trained ML/DL models.

Run with:
    uvicorn ml_service.app.main:app --host 0.0.0.0 --port 8001 --reload
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ml_service.app.serving.model_server import (
    predict_eta_full,
    predict_anomaly,
    get_driver_score,
    get_all_driver_scores,
    get_demand_forecast,
    find_optimal_route,
    get_hub_locations,
    recommend_drivers,
    get_trip_forecast,
    get_model_info,
    list_all_models,
    get_model_comparison,
    load_model,
    clear_cache,
    get_conn,
)

app = FastAPI(
    title="Smart-Truck ML Service",
    description="Machine Learning model serving for fleet analytics. "
                "Provides predictions from 6 trained ML models.",
    version="2.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ETAPredictRequest(BaseModel):
    origin: str = Field(..., description="Origin location name")
    destination: str = Field(..., description="Destination location name")
    driver_id: Optional[int] = Field(None, description="Driver ID")
    vehicle_id: Optional[int] = Field(None, description="Vehicle ID")
    trip_km: Optional[float] = Field(None, description="Trip distance in km")
    trip_start: Optional[str] = Field(None, description="Trip start datetime (ISO format)")


class AnomalyCheckRequest(BaseModel):
    trip_duration_minutes: float
    eta_delay_minutes: float = 0
    duration_ratio: float = 1.0
    delay_ratio: float = 0
    hour_deviation: float = 12
    is_night_trip: int = 0


class RouteOptimizeRequest(BaseModel):
    origin: str
    destination: str
    trip_km: Optional[float] = None
    hour: Optional[int] = Field(None, ge=0, le=23)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)


class DriverRecommendRequest(BaseModel):
    origin: str = Field(..., description="Origin location name")
    destination: str = Field(..., description="Destination location name")
    top_n: int = Field(10, ge=1, le=100, description="Number of drivers to recommend")


class TrainRequest(BaseModel):
    model_name: str = Field(..., description="Model to train")


# ============================================
# HEALTH & INFO
# ============================================

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "smart-truck-ml", "timestamp": datetime.now().isoformat()}


@app.get("/ml")
def ml_root():
    return {
        "message": "Smart-Truck ML Service v2",
        "models": {
            "eta_predictor": "POST /ml/predict/eta - Predict trip ETA (returns expected arrival date/time)",
            "anomaly_detector": "POST /ml/predict/anomaly - Detect trip anomalies",
            "driver_scorer": "GET /ml/drivers/scores - Driver risk/performance scores",
            "demand_forecaster": "GET /ml/forecast/demand - Route demand forecast",
            "route_optimizer": "POST /ml/optimize/route - Find optimal route",
            "driver_recommender": "POST /ml/recommend/drivers - Recommend best drivers for a route",
            "trip_forecaster": "GET /ml/forecast/trips - Forecast expected trips next week",
        },
        "management": {
            "models": "GET /ml/models - List all models",
            "comparison": "GET /ml/models/comparison - Compare active models",
            "train": "POST /ml/train/{model_name} - Train a model",
            "train_all": "POST /ml/train-all - Train all models",
        },
    }


# ============================================
# ETA PREDICTION
# ============================================

@app.post("/ml/predict/eta")
def predict_eta_endpoint(request: ETAPredictRequest):
    """Predict trip duration using ETA model with full feature engineering."""
    conn = get_conn()
    try:
        result = predict_eta_full(conn, {
            "origin": request.origin,
            "destination": request.destination,
            "driver_id": request.driver_id,
            "vehicle_id": request.vehicle_id,
            "trip_km": request.trip_km,
            "trip_start": request.trip_start or datetime.now().isoformat(),
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ============================================
# ANOMALY DETECTION
# ============================================

@app.post("/ml/predict/anomaly")
def predict_anomaly_endpoint(request: AnomalyCheckRequest):
    """Check if a trip is anomalous based on its characteristics."""
    try:
        result = predict_anomaly(request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DRIVER SCORING
# ============================================

@app.get("/ml/drivers/scores")
def get_driver_scores(limit: int = Query(100, ge=1, le=1000)):
    """Get all driver scores ranked by composite score."""
    conn = get_conn()
    try:
        scores = get_all_driver_scores(conn, limit)
        return {"count": len(scores), "drivers": scores}
    finally:
        conn.close()


@app.get("/ml/drivers/{driver_id}/score")
def get_single_driver_score(driver_id: int):
    """Get score for a specific driver."""
    conn = get_conn()
    try:
        score = get_driver_score(conn, driver_id)
        if not score:
            raise HTTPException(status_code=404, detail=f"No score found for driver {driver_id}")
        return score
    finally:
        conn.close()


# ============================================
# DEMAND FORECASTING
# ============================================

@app.get("/ml/forecast/demand")
def forecast_demand(route: Optional[str] = Query(None, description="Route in 'Origin -> Destination' format")):
    """Get demand forecasts for routes."""
    try:
        return get_demand_forecast(route)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ROUTE OPTIMIZATION
# ============================================

@app.post("/ml/optimize/route")
def optimize_route(request: RouteOptimizeRequest):
    """Find optimal route between two locations."""
    try:
        result = find_optimal_route(
            request.origin, request.destination,
            request.trip_km, request.hour, request.day_of_week,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ml/optimize/hubs")
def get_hubs():
    """Get hub location analysis."""
    try:
        return get_hub_locations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DRIVER RECOMMENDER
# ============================================

@app.post("/ml/recommend/drivers")
def recommend_drivers_endpoint(request: DriverRecommendRequest):
    """Recommend best-suited drivers for a given route based on performance, speed, ETA compliance."""
    try:
        result = recommend_drivers(request.origin, request.destination, request.top_n)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# TRIP FORECASTING
# ============================================

@app.get("/ml/forecast/trips")
def forecast_trips(route: Optional[str] = Query(None, description="Route in 'Origin -> Destination' format")):
    """Forecast expected number of trips for next week (fleet-wide or per route)."""
    try:
        result = get_trip_forecast(route)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# MODEL MANAGEMENT
# ============================================

@app.get("/ml/models")
def list_models():
    """List all trained models with their versions and metrics."""
    try:
        models = list_all_models()
        return {"count": len(models), "models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ml/models/comparison")
def compare_models():
    """Compare all active models side by side."""
    try:
        return get_model_comparison()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ml/models/{model_name}")
def get_model_details(model_name: str):
    """Get detailed info about a specific model."""
    try:
        info = get_model_info(model_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"No active model found: {model_name}")
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# TRAINING ENDPOINTS
# ============================================

@app.post("/ml/train/{model_name}")
def train_model(model_name: str, background_tasks: BackgroundTasks):
    """Trigger training for a specific model (runs in background)."""
    from ml_service.app.training.train_pipeline import MODEL_REGISTRY, train_single

    if model_name not in MODEL_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {model_name}. Available: {list(MODEL_REGISTRY.keys())}",
        )

    def _train():
        result = train_single(model_name)
        # Clear cache so next prediction uses new model
        clear_cache(model_name)
        return result

    background_tasks.add_task(_train)
    return {
        "status": "started",
        "model": model_name,
        "description": MODEL_REGISTRY[model_name]["description"],
        "message": f"Training {model_name} in background. Check /ml/models/{model_name} for status.",
    }


@app.post("/ml/train/{model_name}/sync")
def train_model_sync(model_name: str):
    """Trigger training for a specific model (blocks until complete)."""
    from ml_service.app.training.train_pipeline import MODEL_REGISTRY, train_single

    if model_name not in MODEL_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {model_name}. Available: {list(MODEL_REGISTRY.keys())}",
        )

    result = train_single(model_name)
    clear_cache(model_name)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.post("/ml/train-all")
def train_all_models(background_tasks: BackgroundTasks):
    """Trigger training for ALL models (runs in background)."""
    from ml_service.app.training.train_pipeline import train_all

    def _train():
        result = train_all()
        clear_cache()
        return result

    background_tasks.add_task(_train)
    return {
        "status": "started",
        "message": "Training all 6 models in background. Check /ml/models for progress.",
        "models": [
            "eta_predictor", "anomaly_detector", "driver_scorer",
            "demand_forecaster", "route_optimizer", "driver_recommender",
        ],
    }


@app.get("/ml/training/readiness")
def check_training_readiness():
    """Check if the database has enough data for model training."""
    from ml_service.app.training.train_pipeline import check_readiness
    try:
        return check_readiness()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CACHE MANAGEMENT
# ============================================

@app.post("/ml/cache/clear")
def clear_model_cache(model_name: Optional[str] = None):
    """Clear model cache (all or specific model)."""
    clear_cache(model_name)
    return {"status": "ok", "cleared": model_name or "all"}
