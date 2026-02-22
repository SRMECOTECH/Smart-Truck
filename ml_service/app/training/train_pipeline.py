"""
Unified training pipeline for all ML/DL models.
Fetches data from MySQL, trains models, registers in ml_models table.

Usage:
    # Train all models:
    python -m ml_service.app.training.train_pipeline

    # Train specific model:
    python -m ml_service.app.training.train_pipeline --model eta_predictor
    python -m ml_service.app.training.train_pipeline --model anomaly_detector
    python -m ml_service.app.training.train_pipeline --model driver_scorer
    python -m ml_service.app.training.train_pipeline --model demand_forecaster
    python -m ml_service.app.training.train_pipeline --model route_optimizer
    python -m ml_service.app.training.train_pipeline --model driver_recommender

    # Check readiness:
    python -m ml_service.app.training.train_pipeline --check
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "smart_truck"),
    "charset": "utf8mb4",
    "connect_timeout": 30,
    "read_timeout": 300,
    "write_timeout": 300,
}

MODELS_DIR = PROJECT_ROOT / "ml_models"
MODELS_DIR.mkdir(exist_ok=True)


def get_conn():
    return pymysql.connect(**DB_CONFIG, cursorclass=DictCursor)


# ============================================
# INDIVIDUAL MODEL TRAINERS
# ============================================

def train_eta_predictor() -> dict:
    """Train ETA prediction model (XGBoost + LightGBM comparison)."""
    from ml_service.app.models.eta_predictor import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


def train_anomaly_detector() -> dict:
    """Train anomaly detection model (Isolation Forest)."""
    from ml_service.app.models.anomaly_detector import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


def train_driver_scorer() -> dict:
    """Compute driver risk/performance scores."""
    from ml_service.app.models.driver_scorer import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


def train_demand_forecaster() -> dict:
    """Train route demand forecasting model."""
    from ml_service.app.models.demand_forecaster import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


def train_route_optimizer() -> dict:
    """Train route optimization model (Graph + GBRT)."""
    from ml_service.app.models.route_optimizer import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


def train_driver_recommender() -> dict:
    """Train driver recommender model (rank best drivers per route)."""
    from ml_service.app.models.driver_recommender import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


# ============================================
# MODEL REGISTRY MAP
# ============================================

MODEL_REGISTRY = {
    "eta_predictor": {
        "trainer": train_eta_predictor,
        "description": "Trip duration prediction (XGBoost + LightGBM)",
    },
    "anomaly_detector": {
        "trainer": train_anomaly_detector,
        "description": "Trip anomaly detection (Isolation Forest)",
    },
    "driver_scorer": {
        "trainer": train_driver_scorer,
        "description": "Driver risk/performance scoring (weighted + penalty)",
    },
    "demand_forecaster": {
        "trainer": train_demand_forecaster,
        "description": "Route demand forecasting (Exponential Smoothing + Ridge)",
    },
    "route_optimizer": {
        "trainer": train_route_optimizer,
        "description": "Route optimization (Graph + Gradient Boosting)",
    },
    "driver_recommender": {
        "trainer": train_driver_recommender,
        "description": "Driver recommendation/ranking per route",
    },
}


# ============================================
# TRAIN ALL
# ============================================

def train_all() -> dict:
    """Train every model in sequence."""
    logger.info("=" * 60)
    logger.info("SMART-TRUCK ML TRAINING PIPELINE")
    logger.info(f"Models dir: {MODELS_DIR}")
    logger.info(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"Models to train: {len(MODEL_REGISTRY)}")
    logger.info("=" * 60)

    results = {}
    start_time = datetime.now()

    for model_name, config in MODEL_REGISTRY.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"[{model_name}] {config['description']}")
        logger.info(f"{'='*60}")

        model_start = datetime.now()
        try:
            result = config["trainer"]()
            duration = (datetime.now() - model_start).total_seconds()
            result["training_time_seconds"] = round(duration, 2)
            results[model_name] = result
            logger.info(f"[OK] {model_name} completed in {duration:.1f}s")
        except Exception as e:
            duration = (datetime.now() - model_start).total_seconds()
            logger.error(f"[FAIL] {model_name} failed: {e}", exc_info=True)
            results[model_name] = {
                "error": str(e),
                "training_time_seconds": round(duration, 2),
            }

    total_time = (datetime.now() - start_time).total_seconds()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING SUMMARY")
    logger.info("=" * 60)

    success_count = sum(1 for r in results.values() if "error" not in r)
    fail_count = len(results) - success_count

    for name, result in results.items():
        status = "OK" if "error" not in result else "FAIL"
        time_taken = result.get("training_time_seconds", 0)
        logger.info(f"  [{status}] {name} ({time_taken:.1f}s)")
        if "error" in result:
            logger.info(f"        Error: {result['error']}")

    logger.info(f"\nTotal: {success_count} succeeded, {fail_count} failed")
    logger.info(f"Total training time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    logger.info("=" * 60)

    return results


def train_single(model_name: str) -> dict:
    """Train a single model by name."""
    if model_name not in MODEL_REGISTRY:
        available = ", ".join(MODEL_REGISTRY.keys())
        raise ValueError(f"Unknown model: {model_name}. Available: {available}")

    config = MODEL_REGISTRY[model_name]
    logger.info(f"Training: {model_name} - {config['description']}")

    start_time = datetime.now()
    try:
        result = config["trainer"]()
        result["training_time_seconds"] = round((datetime.now() - start_time).total_seconds(), 2)
        logger.info(f"[OK] {model_name} completed in {result['training_time_seconds']:.1f}s")
        return result
    except Exception as e:
        logger.error(f"[FAIL] {model_name} failed: {e}", exc_info=True)
        return {
            "error": str(e),
            "training_time_seconds": round((datetime.now() - start_time).total_seconds(), 2),
        }


# ============================================
# UTILITY: Check training readiness
# ============================================

def check_readiness() -> dict:
    """Check if the database has enough data for training."""
    logger.info("Checking training readiness...")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            checks = {}

            # Check main tables
            for table in ["trips", "drivers", "vehicles", "locations",
                          "driver_summary", "route_summary", "vehicle_summary",
                          "daily_fleet_stats", "route_time_patterns"]:
                try:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                    checks[table] = cur.fetchone()["cnt"]
                except Exception:
                    checks[table] = -1  # table doesn't exist

            # Specific checks
            cur.execute("""
                SELECT COUNT(*) AS cnt FROM trips
                WHERE trip_duration_minutes IS NOT NULL AND trip_duration_minutes > 0
            """)
            checks["trips_with_duration"] = cur.fetchone()["cnt"]

            # Check if summaries are populated
            checks["ready"] = (
                checks.get("trips_with_duration", 0) >= 100
                and checks.get("driver_summary", 0) >= 10
                and checks.get("route_summary", 0) >= 10
            )

            if not checks["ready"]:
                checks["message"] = (
                    "Not ready. Ensure data is migrated and summaries are refreshed:\n"
                    "  1. POST /api/v1/migrate/schema\n"
                    "  2. POST /api/v1/migrate/trips/sync\n"
                    "  3. POST /api/v1/migrate/refresh-summaries\n"
                    "Then re-run training."
                )
            else:
                checks["message"] = (
                    f"Ready! {checks['trips_with_duration']:,} trips, "
                    f"{checks.get('driver_summary', 0):,} drivers, "
                    f"{checks.get('route_summary', 0):,} routes"
                )

            logger.info(checks["message"])
            return checks
    finally:
        conn.close()


# ============================================
# CLI ENTRY POINT
# ============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smart-Truck ML/DL Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ml_service.app.training.train_pipeline              # Train all 7 models
  python -m ml_service.app.training.train_pipeline -m eta_predictor   # Train specific model
  python -m ml_service.app.training.train_pipeline --check      # Check database readiness
  python -m ml_service.app.training.train_pipeline --list       # List available models

Available models:
  eta_predictor       - Trip duration prediction (XGBoost + LightGBM)
  anomaly_detector    - Trip anomaly detection (Isolation Forest)
  driver_scorer       - Driver risk scoring (weighted formula)
  demand_forecaster   - Route demand forecasting (ES + Ridge)
  route_optimizer     - Route optimization (Graph + GBRT)
  driver_recommender  - Driver recommendation/ranking per route
        """,
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Train specific model (omit to train all).",
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check if database is ready for training.",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available models.",
    )

    args = parser.parse_args()

    if args.list:
        print("\nAvailable models:")
        for name, config in MODEL_REGISTRY.items():
            print(f"  {name:20s} - {config['description']}")
        print()
    elif args.check:
        readiness = check_readiness()
        print(json.dumps(readiness, indent=2))
    elif args.model:
        result = train_single(args.model)
        print(json.dumps(result, indent=2, default=str))
    else:
        results = train_all()
        print(json.dumps(results, indent=2, default=str))
