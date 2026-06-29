"""
Unified training pipeline for all ML/DL models.
Supports: individual training, train-all, scheduled tiers (daily/weekly/monthly).

Usage:
    # Train all models:
    python -m ml_service.app.training.train_pipeline

    # Train specific model:
    python -m ml_service.app.training.train_pipeline --model eta_predictor

    # Scheduled tiers:
    python -m ml_service.app.training.train_pipeline --tier daily
    python -m ml_service.app.training.train_pipeline --tier weekly
    python -m ml_service.app.training.train_pipeline --tier monthly

    # Check readiness:
    python -m ml_service.app.training.train_pipeline --check
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from config.database import get_conn
from config.logging_config import setup_logging

# Setup logging when run as a standalone script
if __name__ == "__main__" or not logging.getLogger().handlers:
    setup_logging(service_name="ml-train")

logger = logging.getLogger(__name__)

MODELS_DIR = Path(settings.ML_MODELS_DIR)
MODELS_DIR.mkdir(exist_ok=True)


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


def train_sla_predictor() -> dict:
    """Train SLA / on-time delivery prediction model (XGBoost classifier)."""
    from ml_service.app.models.sla_predictor import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


def train_fatigue_predictor() -> dict:
    """Train driver fatigue / risk prediction model."""
    from ml_service.app.models.fatigue_predictor import train
    conn = get_conn()
    try:
        return train(conn, MODELS_DIR)
    finally:
        conn.close()


def train_client_demand_forecaster() -> dict:
    """Train client/company demand forecasting model."""
    from ml_service.app.models.client_demand_forecaster import train
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
        "tier": "weekly",
    },
    "anomaly_detector": {
        "trainer": train_anomaly_detector,
        "description": "Trip anomaly detection (Isolation Forest)",
        "tier": "weekly",
    },
    "driver_scorer": {
        "trainer": train_driver_scorer,
        "description": "Driver risk/performance scoring (weighted + penalty)",
        "tier": "daily",
    },
    "demand_forecaster": {
        "trainer": train_demand_forecaster,
        "description": "Route demand forecasting (Exponential Smoothing + Ridge)",
        "tier": "weekly",
    },
    "route_optimizer": {
        "trainer": train_route_optimizer,
        "description": "Route optimization (Graph + Gradient Boosting)",
        "tier": "monthly",
    },
    "driver_recommender": {
        "trainer": train_driver_recommender,
        "description": "Driver recommendation/ranking per route",
        "tier": "daily",
    },
    "sla_predictor": {
        "trainer": train_sla_predictor,
        "description": "SLA / on-time delivery prediction (XGBoost classifier)",
        "tier": "weekly",
    },
    "fatigue_predictor": {
        "trainer": train_fatigue_predictor,
        "description": "Driver fatigue / risk prediction",
        "tier": "daily",
    },
    "client_demand_forecaster": {
        "trainer": train_client_demand_forecaster,
        "description": "Client/company demand forecasting (trips per client per week)",
        "tier": "weekly",
    },
}

# ============================================
# SCHEDULED TRAINING TIERS
# ============================================

# Daily: lightweight models that use pre-computed summaries
# Weekly: heavier ML models trained on raw trip data
# Monthly: expensive graph/optimization models

TRAINING_TIERS = {
    "daily": {
        "description": "Lightweight daily models: driver scores, recommender, fatigue",
        "models": ["driver_scorer", "driver_recommender", "fatigue_predictor"],
        "pre_tasks": ["refresh_summaries_incremental"],
    },
    "weekly": {
        "description": "ML models trained on trip data: ETA, anomaly, demand, SLA",
        "models": ["eta_predictor", "anomaly_detector", "demand_forecaster", "sla_predictor", "client_demand_forecaster"],
        "pre_tasks": ["refresh_summaries_full"],
    },
    "monthly": {
        "description": "Full retrain of all models including expensive ones",
        "models": list(MODEL_REGISTRY.keys()),
        "pre_tasks": ["refresh_summaries_full"],
    },
}


def run_pre_tasks(tasks: list):
    """Run pre-training tasks like summary refresh."""
    for task in tasks:
        if task == "refresh_summaries_incremental":
            logger.info("Pre-task: Incremental summary refresh")
            from scripts.refresh_summaries import refresh_incremental
            conn = get_conn()
            try:
                refresh_incremental(conn)
            finally:
                conn.close()
        elif task == "refresh_summaries_full":
            logger.info("Pre-task: Full summary refresh")
            from migrations.migrate_data import refresh_summaries
            conn = get_conn()
            try:
                refresh_summaries(conn)
            finally:
                conn.close()


def train_tier(tier_name: str) -> dict:
    """Train all models in a specific tier with pre-tasks."""
    if tier_name not in TRAINING_TIERS:
        available = ", ".join(TRAINING_TIERS.keys())
        raise ValueError(f"Unknown tier: {tier_name}. Available: {available}")

    tier = TRAINING_TIERS[tier_name]
    logger.info("=" * 60)
    logger.info(f"SCHEDULED TRAINING: {tier_name.upper()} tier")
    logger.info(f"Description: {tier['description']}")
    logger.info(f"Models: {tier['models']}")
    logger.info("=" * 60)

    # Run pre-tasks
    run_pre_tasks(tier.get("pre_tasks", []))

    # Train models
    results = {}
    start_time = datetime.now()

    for model_name in tier["models"]:
        config = MODEL_REGISTRY[model_name]
        logger.info(f"\n[{model_name}] {config['description']}")

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
    success_count = sum(1 for r in results.values() if "error" not in r)

    logger.info(f"\nTier {tier_name}: {success_count}/{len(results)} succeeded in {total_time:.1f}s")

    return {
        "tier": tier_name,
        "results": results,
        "total_time_seconds": round(total_time, 2),
    }


# ============================================
# TRAIN ALL
# ============================================

def train_all() -> dict:
    """Train every model in sequence."""
    logger.info("=" * 60)
    logger.info("SMART-TRUCK ML TRAINING PIPELINE")
    logger.info(f"Models dir: {MODELS_DIR}")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
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
  python -m ml_service.app.training.train_pipeline              # Train all models
  python -m ml_service.app.training.train_pipeline -m eta_predictor
  python -m ml_service.app.training.train_pipeline --tier daily  # Daily tier
  python -m ml_service.app.training.train_pipeline --tier weekly # Weekly tier
  python -m ml_service.app.training.train_pipeline --check       # Check readiness
  python -m ml_service.app.training.train_pipeline --list        # List models

Training Tiers:
  daily   - Driver scores, recommender, fatigue (fast, uses summaries)
  weekly  - ETA, anomaly, demand, SLA (heavier, trains on raw data)
  monthly - All models including route optimizer (full retrain)
        """,
    )
    parser.add_argument("--model", "-m", type=str, default=None, help="Train specific model")
    parser.add_argument("--tier", "-t", type=str, default=None, help="Run training tier: daily/weekly/monthly")
    parser.add_argument("--check", "-c", action="store_true", help="Check database readiness")
    parser.add_argument("--list", "-l", action="store_true", help="List all available models")

    args = parser.parse_args()

    if args.list:
        print("\nAvailable models:")
        for name, config in MODEL_REGISTRY.items():
            tier = config.get("tier", "manual")
            print(f"  {name:22s} [{tier:7s}] {config['description']}")
        print("\nTraining tiers:")
        for tier_name, tier in TRAINING_TIERS.items():
            print(f"  {tier_name:10s} - {tier['description']}")
        print()
    elif args.check:
        readiness = check_readiness()
        print(json.dumps(readiness, indent=2))
    elif args.tier:
        result = train_tier(args.tier)
        print(json.dumps(result, indent=2, default=str))
    elif args.model:
        result = train_single(args.model)
        print(json.dumps(result, indent=2, default=str))
    else:
        results = train_all()
        print(json.dumps(results, indent=2, default=str))
