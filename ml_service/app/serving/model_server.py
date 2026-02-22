"""
Model serving: loads active models from disk, caches in memory, serves predictions.
Handles 6 models: ETA, Anomaly, Driver Scorer, Demand Forecaster, Route Optimizer, Driver Recommender.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Optional, List

import pandas as pd
import numpy as np
import joblib
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "ml_models"

# In-memory model cache
_model_cache: Dict[str, object] = {}

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "smart_truck",
    "charset": "utf8mb4",
}


def get_conn():
    return pymysql.connect(**DB_CONFIG, cursorclass=DictCursor)


# ============================================
# MODEL LOADING
# ============================================

def load_model(model_name: str, force_reload: bool = False):
    """Load a model from disk (or cache). Returns the artifact dict or model object."""
    if model_name in _model_cache and not force_reload:
        return _model_cache[model_name]

    # Try database first for path
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT model_artifact_path FROM ml_models WHERE model_name = %s AND is_active = 1 LIMIT 1",
                (model_name,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    # If database has path, use it; otherwise try default path
    if row and row["model_artifact_path"]:
        path = row["model_artifact_path"]
    else:
        path = str(MODELS_DIR / f"{model_name}.joblib")

    if not Path(path).exists():
        logger.warning(f"Model file not found: {path}")
        return None

    artifact = joblib.load(path)
    _model_cache[model_name] = artifact
    logger.info(f"Loaded model: {model_name} from {path}")
    return artifact


def clear_cache(model_name: str = None):
    """Clear model cache (all or specific model)."""
    if model_name:
        _model_cache.pop(model_name, None)
    else:
        _model_cache.clear()
    logger.info(f"Cache cleared: {'all' if not model_name else model_name}")


# ============================================
# ETA PREDICTION
# ============================================

def predict_eta(features_df: pd.DataFrame) -> Optional[float]:
    """Predict trip duration in minutes."""
    artifact = load_model("eta_predictor")
    if artifact is None:
        return None

    # Handle both dict artifact (from eta_predictor.py) and raw model
    if isinstance(artifact, dict) and "model" in artifact:
        model = artifact["model"]
        feature_cols = artifact.get("feature_columns", [])
        if feature_cols:
            for col in feature_cols:
                if col not in features_df.columns:
                    features_df[col] = 0
            features_df = features_df[feature_cols]
    else:
        model = artifact

    prediction = model.predict(features_df)[0]
    return round(float(max(0, prediction)), 2)


def predict_eta_full(conn, trip_data: dict) -> dict:
    """Full ETA prediction with feature engineering from raw trip data."""
    from ml_service.app.features.feature_engineering import (
        extract_temporal_features,
        get_route_features,
        get_driver_features,
        get_vehicle_features,
        get_time_pattern_features,
        build_feature_vector,
        ETA_FEATURE_COLUMNS,
    )

    # Extract all features
    temporal = extract_temporal_features(trip_data.get("trip_start"))
    route = get_route_features(conn, trip_data.get("origin", ""), trip_data.get("destination", ""))
    driver = get_driver_features(conn, trip_data.get("driver_id", 0))
    vehicle = get_vehicle_features(conn, trip_data.get("vehicle_id", 0))
    time_pattern = get_time_pattern_features(
        conn,
        trip_data.get("origin", ""),
        trip_data.get("destination", ""),
        temporal.get("hour", 0),
        temporal.get("day_of_week", 0),
    )

    feature_df = build_feature_vector(
        temporal, route, driver, vehicle, time_pattern,
        trip_km=trip_data.get("trip_km"),
    )

    # Ensure columns match
    for col in ETA_FEATURE_COLUMNS:
        if col not in feature_df.columns:
            feature_df[col] = 0
    feature_df = feature_df[ETA_FEATURE_COLUMNS].fillna(0).astype(float)

    predicted_duration = predict_eta(feature_df)

    return {
        "predicted_duration_minutes": predicted_duration,
        "features_used": {k: round(float(v), 4) for k, v in feature_df.iloc[0].to_dict().items()},
        "route_avg_duration": route.get("route_avg_duration"),
        "driver_avg_duration": driver.get("driver_avg_duration"),
    }


# ============================================
# ANOMALY DETECTION
# ============================================

def predict_anomaly(trip_data: dict) -> dict:
    """Score a single trip for anomaly."""
    artifact = load_model("anomaly_detector")
    if artifact is None:
        return {"anomaly_score": None, "is_anomalous": None, "error": "Model not loaded"}

    from ml_service.app.models.anomaly_detector import predict
    return predict(artifact, trip_data)


# ============================================
# DRIVER SCORING
# ============================================

def get_driver_score(conn, driver_id: int) -> Optional[dict]:
    """Get the latest driver score from predictions table."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.predicted_value AS composite_score, p.input_features, p.created_at
            FROM predictions p
            JOIN ml_models m ON p.model_id = m.id
            WHERE m.model_name = 'driver_scorer' AND m.is_active = 1
              AND p.driver_id = %s
            ORDER BY p.created_at DESC
            LIMIT 1
        """, (driver_id,))
        row = cur.fetchone()

    if not row:
        return None

    scores = json.loads(row["input_features"]) if isinstance(row["input_features"], str) else row["input_features"]

    return {
        "driver_id": driver_id,
        "composite_score": float(row["composite_score"]),
        "scores": scores,
        "scored_at": str(row["created_at"]),
    }


def get_all_driver_scores(conn, limit: int = 100) -> list:
    """Get all driver scores, sorted by composite score."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.driver_id, d.name AS driver_name,
                   p.predicted_value AS composite_score, p.input_features
            FROM predictions p
            JOIN ml_models m ON p.model_id = m.id
            LEFT JOIN drivers d ON p.driver_id = d.id
            WHERE m.model_name = 'driver_scorer' AND m.is_active = 1
              AND p.prediction_type = 'driver_score'
            ORDER BY p.predicted_value DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()

    results = []
    for row in rows:
        scores = json.loads(row["input_features"]) if isinstance(row["input_features"], str) else row["input_features"]
        results.append({
            "driver_id": row["driver_id"],
            "driver_name": row["driver_name"],
            "composite_score": float(row["composite_score"]),
            "risk_level": scores.get("risk_level", "unknown"),
            "scores": scores,
        })
    return results


# ============================================
# DEMAND FORECASTING
# ============================================

def get_demand_forecast(route: str = None) -> dict:
    """Get demand forecasts (all routes or specific route)."""
    artifact = load_model("demand_forecaster")
    if artifact is None:
        return {"error": "Model not loaded"}

    forecasts = artifact.get("forecasts", {})
    generated_at = artifact.get("generated_at", "unknown")

    if route:
        if route in forecasts:
            return {"route": route, "forecast": forecasts[route], "generated_at": generated_at}
        return {"error": f"No forecast for route: {route}"}

    return {
        "routes_count": len(forecasts),
        "generated_at": generated_at,
        "forecasts": forecasts,
    }


# ============================================
# ROUTE OPTIMIZATION
# ============================================

def find_optimal_route(origin: str, destination: str,
                       trip_km: float = None, hour: int = None,
                       day_of_week: int = None) -> dict:
    """Find optimal route between locations."""
    artifact = load_model("route_optimizer")
    if artifact is None:
        return {"error": "Model not loaded"}

    from ml_service.app.models.route_optimizer import find_optimal_route as _find
    return _find(artifact, origin, destination, trip_km, hour, day_of_week)


def get_hub_locations() -> dict:
    """Get hub analysis from route optimizer."""
    artifact = load_model("route_optimizer")
    if artifact is None:
        return {"error": "Model not loaded"}

    from ml_service.app.models.route_optimizer import get_hub_locations as _get_hubs
    return _get_hubs(artifact)


# ============================================
# DRIVER RECOMMENDER
# ============================================

def recommend_drivers(origin: str, destination: str, top_n: int = 10) -> dict:
    """Recommend best drivers for a given route."""
    artifact = load_model("driver_recommender")
    if artifact is None:
        return {"error": "Driver recommender model not loaded. Train it first via POST /ml/train/driver_recommender"}

    from ml_service.app.models.driver_recommender import recommend_drivers as _recommend
    return _recommend(artifact, origin, destination, top_n)


# ============================================
# TRIP FORECASTING
# ============================================

def get_trip_forecast(route: str = None) -> dict:
    """Get trip forecasts (fleet-wide or specific route)."""
    artifact = load_model("demand_forecaster")
    if artifact is None:
        return {"error": "Demand forecaster model not loaded. Train it first via POST /ml/train/demand_forecaster"}

    forecasts = artifact.get("forecasts", {})
    fleet_forecast = artifact.get("fleet_forecast", {})
    generated_at = artifact.get("generated_at", "unknown")

    if route:
        if route in forecasts:
            return {"route": route, "forecast": forecasts[route], "generated_at": generated_at}
        return {"error": f"No forecast for route: {route}"}

    # Fleet-wide summary
    return {
        "fleet_forecast": fleet_forecast,
        "routes_count": len(forecasts),
        "generated_at": generated_at,
        "top_routes": {r: forecasts[r] for r in list(forecasts.keys())[:10]},
    }


# ============================================
# MODEL INFO & LISTING
# ============================================

def get_model_info(model_name: str) -> Optional[dict]:
    """Get model metadata from database."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, model_name, version, model_type, target_variable,
                       metrics, feature_columns, training_data_count,
                       is_active, trained_at
                FROM ml_models
                WHERE model_name = %s AND is_active = 1
                LIMIT 1
            """, (model_name,))
            row = cur.fetchone()
    finally:
        conn.close()

    if row:
        row["trained_at"] = str(row["trained_at"]) if row["trained_at"] else None
        if isinstance(row.get("metrics"), str):
            row["metrics"] = json.loads(row["metrics"])
        if isinstance(row.get("feature_columns"), str):
            row["feature_columns"] = json.loads(row["feature_columns"])
    return row


def list_all_models() -> list:
    """List all models (active and inactive) from database."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, model_name, version, model_type, target_variable,
                       metrics, training_data_count, is_active, trained_at
                FROM ml_models
                ORDER BY model_name, version DESC
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    for r in rows:
        r["trained_at"] = str(r["trained_at"]) if r["trained_at"] else None
        if isinstance(r.get("metrics"), str):
            r["metrics"] = json.loads(r["metrics"])
    return rows


def get_model_comparison() -> dict:
    """Compare all active models side by side."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT model_name, version, model_type, metrics,
                       training_data_count, trained_at
                FROM ml_models
                WHERE is_active = 1
                ORDER BY model_name
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    comparison = {}
    for r in rows:
        metrics = json.loads(r["metrics"]) if isinstance(r["metrics"], str) else (r["metrics"] or {})
        comparison[r["model_name"]] = {
            "version": r["version"],
            "model_type": r["model_type"],
            "training_data": r["training_data_count"],
            "trained_at": str(r["trained_at"]) if r["trained_at"] else None,
            "metrics": metrics,
        }

    return comparison
