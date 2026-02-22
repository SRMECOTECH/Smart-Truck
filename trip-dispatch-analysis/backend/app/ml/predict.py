"""
ETA Prediction Module

Loads the trained model and provides prediction functions
used by the FastAPI endpoint.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import psycopg2
from psycopg2.extras import RealDictCursor

# Support both standalone run (from app/) and import from uvicorn (from backend/)
try:
    from app.ml.features import prepare_prediction_features, get_feature_columns
except ImportError:
    from ml.features import prepare_prediction_features, get_feature_columns

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "eta_model.pkl"
METADATA_PATH = MODEL_DIR / "eta_model_metadata.json"

# Module-level cache for loaded model
_model = None
_metadata = None


def load_model():
    """Load the trained model from disk (cached after first load)."""
    global _model, _metadata

    if _model is not None:
        return _model, _metadata

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No trained model found at {MODEL_PATH}. Run 'python -m ml.train' first."
        )

    _model = joblib.load(MODEL_PATH)
    logger.info(f"Loaded model from {MODEL_PATH}")

    if METADATA_PATH.exists():
        with open(METADATA_PATH) as f:
            _metadata = json.load(f)
        logger.info(f"Model trained at: {_metadata.get('trained_at')}")
        logger.info(f"Model R2 score: {_metadata.get('metrics', {}).get('r2_score')}")
    else:
        _metadata = {}

    return _model, _metadata


def reload_model():
    """Force reload the model (call after retraining)."""
    global _model, _metadata
    _model = None
    _metadata = None
    return load_model()


def fetch_route_stats_for_prediction(conn, origin: str, destination: str) -> dict:
    """Fetch route stats from mv_route_summary for a specific route."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM mv_route_summary WHERE origin = %s AND destination = %s",
            (origin, destination),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def fetch_driver_stats_for_prediction(conn, driver_name: str) -> tuple:
    """Fetch driver stats from mv_driver_summary. Returns (driver_id, stats_dict)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM mv_driver_summary WHERE driver_name = %s",
            (driver_name,),
        )
        row = cur.fetchone()
    if row:
        return int(row["driver_id"]), dict(row)
    return None, None


def predict_eta_ml(
    conn,
    origin: str,
    destination: str,
    trip_start_str: str,
    driver_name: str = None,
) -> dict:
    """
    Predict ETA using the trained ML model.

    Parameters:
        conn: Database connection
        origin: Origin location name
        destination: Destination location name
        trip_start_str: Trip start time as ISO string (e.g. "2024-01-15T10:30:00")
        driver_name: Optional driver name

    Returns:
        Dict with prediction results
    """
    model, metadata = load_model()

    # Parse trip start time
    try:
        trip_start = datetime.fromisoformat(trip_start_str)
    except ValueError:
        return {"error": f"Invalid datetime format: {trip_start_str}. Use ISO format like 2024-01-15T10:30:00"}

    # Fetch route stats
    route_stats = fetch_route_stats_for_prediction(conn, origin, destination)

    # Fetch driver stats
    driver_id = None
    driver_stats = None
    if driver_name:
        driver_id, driver_stats = fetch_driver_stats_for_prediction(conn, driver_name)
        if not driver_stats:
            logger.warning(f"Driver '{driver_name}' not found, predicting without driver features")

    # Check if route exists
    if not route_stats:
        return {
            "prediction_available": False,
            "message": f"No historical data found for route {origin} -> {destination}",
            "origin": origin,
            "destination": destination,
        }

    # Build feature vector
    features_df = prepare_prediction_features(
        origin=origin,
        destination=destination,
        trip_start=trip_start,
        driver_id=driver_id,
        driver_stats_row=driver_stats,
        route_stats_row=route_stats,
    )

    # Predict
    predicted_duration = model.predict(features_df)[0]
    predicted_duration = max(predicted_duration, 10)  # minimum 10 minutes

    predicted_arrival = trip_start + timedelta(minutes=predicted_duration)

    # Confidence based on route data volume + driver availability
    route_trip_count = int(route_stats.get("trip_count", 0))
    if route_trip_count >= 50 and driver_stats:
        confidence = "high"
    elif route_trip_count >= 50:
        confidence = "high"
    elif route_trip_count >= 10:
        confidence = "medium"
    else:
        confidence = "low"

    result = {
        "prediction_available": True,
        "origin": origin,
        "destination": destination,
        "trip_start": trip_start.isoformat(),
        "predicted_duration_minutes": round(float(predicted_duration), 2),
        "predicted_duration_hours": round(float(predicted_duration / 60), 2),
        "predicted_arrival": predicted_arrival.isoformat(),
        "confidence": confidence,
        "route_historical_avg_minutes": round(float(route_stats.get("avg_duration_min", 0) or 0), 2),
        "route_historical_avg_hours": round(float(route_stats.get("avg_duration_min", 0) or 0) / 60, 2),
        "route_trip_count": route_trip_count,
        "model_type": "ml",
    }

    if driver_name and driver_stats:
        result["driver_name"] = driver_name
        result["driver_avg_duration_minutes"] = round(float(driver_stats.get("avg_duration_min", 0) or 0), 2)
        result["driver_eta_success_rate"] = round(float(driver_stats.get("eta_success_rate", 0) or 0), 2)

    if metadata:
        result["model_metrics"] = {
            "r2_score": metadata.get("metrics", {}).get("r2_score"),
            "mae_hours": metadata.get("metrics", {}).get("mae_hours"),
            "trained_at": metadata.get("trained_at"),
        }

    return result
