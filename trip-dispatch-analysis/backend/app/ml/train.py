"""
ETA Prediction Model Training Pipeline

Fetches trip data from PostgreSQL, engineers features, trains an XGBoost
regression model, evaluates it, and saves the artifact to ml/models/.

Updated to include arrival-time accuracy metrics and validation reporting.
"""

import os
import sys
import json
import logging
import warnings
import psycopg2
import pandas as pd
import numpy as np
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from pathlib import Path

# Suppress pandas SQLAlchemy warning (we use psycopg2 directly, which works fine)
warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import GradientBoostingRegressor
import joblib

# Add parent directory to path so we can import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Support both standalone run (from app/) and import from uvicorn (from backend/)
try:
    from ..config import DATABASE_URL
    from .features import build_training_features, get_feature_columns, TARGET_COLUMN
except ImportError:
    try:
        from config import DATABASE_URL
        from ml.features import build_training_features, get_feature_columns, TARGET_COLUMN
    except ImportError:
        from app.config import DATABASE_URL
        from app.ml.features import build_training_features, get_feature_columns, TARGET_COLUMN

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "eta_model.pkl"
METADATA_PATH = MODEL_DIR / "eta_model_metadata.json"
VALIDATION_REPORT_PATH = MODEL_DIR / "validation_report.csv"


def fetch_training_data(conn) -> pd.DataFrame:
    """Fetch completed trip data with origin/destination names and driver info."""
    logger.info("Fetching trip data from database...")
    sql = """
        SELECT
            t.trip_start,
            t.trip_end,
            t.ata_in,
            t.trip_duration_minutes,
            t.trip_km,
            t.avg_speed_kmph,
            t.eta_met,
            t.eta_delay_minutes,
            t.driver_id,
            lo.name AS origin,
            ld.name AS destination,
            v.asset_type
        FROM trips t
        JOIN locations lo ON t.origin_id = lo.id
        JOIN locations ld ON t.destination_id = ld.id
        LEFT JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.trip_start IS NOT NULL
          AND t.trip_end IS NOT NULL
          AND t.ata_in IS NOT NULL
          AND t.trip_duration_minutes IS NOT NULL
          AND t.trip_duration_minutes > 0
          AND t.trip_status = 'C'
    """
    df = pd.read_sql(sql, conn)
    df["trip_start"] = pd.to_datetime(df["trip_start"])
    df["trip_end"] = pd.to_datetime(df["trip_end"])
    df["ata_in"] = pd.to_datetime(df["ata_in"])
    logger.info(f"Fetched {len(df)} completed trips")
    return df


def fetch_driver_stats(conn) -> pd.DataFrame:
    """Fetch pre-aggregated driver statistics."""
    logger.info("Fetching driver stats...")
    sql = """
        SELECT
            driver_id,
            avg_duration_min AS driver_avg_duration,
            avg_speed_kmph AS driver_avg_speed,
            eta_success_rate AS driver_eta_success_rate,
            total_trips AS driver_total_trips,
            avg_distance_km AS driver_avg_distance
        FROM mv_driver_summary
    """
    df = pd.read_sql(sql, conn)
    # Convert Decimal to float
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            df[col] = df[col].astype(float)
        except (ValueError, TypeError):
            pass
    for col in df.select_dtypes(include=["number"]).columns:
        df[col] = df[col].astype(float)
    logger.info(f"Fetched stats for {len(df)} drivers")
    return df


def fetch_route_stats(conn) -> pd.DataFrame:
    """Fetch pre-aggregated route statistics."""
    logger.info("Fetching route stats...")
    sql = """
        SELECT
            origin,
            destination,
            avg_duration_min AS route_avg_duration,
            avg_distance_km AS route_avg_distance,
            trip_count AS route_trip_count,
            eta_success_rate AS route_eta_success_rate
        FROM mv_route_summary
    """
    df = pd.read_sql(sql, conn)
    for col in df.select_dtypes(include=["number"]).columns:
        df[col] = df[col].astype(float)
    logger.info(f"Fetched stats for {len(df)} routes")
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Remove outliers and bad data."""
    initial = len(df)

    # Remove trips shorter than 10 minutes (likely data errors)
    df = df[df["trip_duration_minutes"] >= 10]

    # Remove extreme outliers: trips longer than 15 days (21600 minutes)
    df = df[df["trip_duration_minutes"] <= 21600]

    # Remove trips with negative or zero duration
    df = df[df["trip_duration_minutes"] > 0]

    # Use IQR-based outlier removal per route for more precision
    def remove_route_outliers(group):
        q1 = group["trip_duration_minutes"].quantile(0.05)
        q3 = group["trip_duration_minutes"].quantile(0.95)
        return group[(group["trip_duration_minutes"] >= q1) & (group["trip_duration_minutes"] <= q3)]

    # Only apply per-route outlier removal on routes with enough data
    route_counts = df.groupby(["origin", "destination"]).size()
    frequent_routes = route_counts[route_counts >= 10].index
    mask_frequent = df.set_index(["origin", "destination"]).index.isin(frequent_routes)

    df_frequent = df[mask_frequent].groupby(["origin", "destination"], group_keys=False).apply(remove_route_outliers)
    df_infrequent = df[~mask_frequent]
    df = pd.concat([df_frequent, df_infrequent], ignore_index=True)

    removed = initial - len(df)
    logger.info(f"Cleaned data: {initial} -> {len(df)} trips (removed {removed} outliers)")
    return df


def train_model(X_train, y_train):
    """Train a Gradient Boosting Regressor."""
    logger.info("Training model...")
    model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
    )
    model.fit(X_train, y_train)
    logger.info("Model training complete")
    return model


def evaluate_model(model, X_test, y_test) -> dict:
    """Evaluate model and return metrics."""
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    # Mean Absolute Percentage Error (only where y_test > 0)
    mask = y_test > 0
    mape = np.mean(np.abs((y_test[mask] - y_pred[mask]) / y_test[mask])) * 100

    # Percentage of predictions within 20% of actual
    within_20_pct = np.mean(np.abs(y_pred - y_test) / y_test <= 0.20) * 100

    metrics = {
        "mae_minutes": round(float(mae), 2),
        "mae_hours": round(float(mae / 60), 2),
        "rmse_minutes": round(float(rmse), 2),
        "r2_score": round(float(r2), 4),
        "mape_percent": round(float(mape), 2),
        "within_20_pct_accuracy": round(float(within_20_pct), 2),
        "test_samples": int(len(y_test)),
    }

    logger.info("=== Model Evaluation (Duration Metrics) ===")
    logger.info(f"  MAE:  {metrics['mae_minutes']} min ({metrics['mae_hours']} hrs)")
    logger.info(f"  RMSE: {metrics['rmse_minutes']} min")
    logger.info(f"  R2:   {metrics['r2_score']}")
    logger.info(f"  MAPE: {metrics['mape_percent']}%")
    logger.info(f"  Within 20% accuracy: {metrics['within_20_pct_accuracy']}%")

    return metrics


def evaluate_arrival_accuracy(model, X_test, trip_start_test, ata_in_test) -> dict:
    """
    Evaluate model accuracy in terms of predicted vs actual arrival times.

    Parameters:
        model: Trained model
        X_test: Test features
        trip_start_test: Test set trip start times (Series of datetime)
        ata_in_test: Test set actual arrival times (Series of datetime)

    Returns:
        Dict with arrival-based metrics
    """
    logger.info("=== Evaluating Arrival Time Accuracy ===")

    # Predict durations
    predicted_duration_minutes = model.predict(X_test)

    # Convert to timedeltas and calculate predicted arrivals
    predicted_arrivals = trip_start_test + pd.to_timedelta(predicted_duration_minutes, unit='m')
    actual_arrivals = ata_in_test

    # Calculate arrival errors in hours
    arrival_errors = (predicted_arrivals - actual_arrivals).dt.total_seconds() / 3600
    arrival_errors_abs = np.abs(arrival_errors)

    # Metrics
    mean_error_hours = float(np.mean(arrival_errors_abs))
    median_error_hours = float(np.median(arrival_errors_abs))
    bias_hours = float(np.mean(arrival_errors))  # Positive = predicting late, negative = early

    # Percentage within time windows
    within_1h_pct = float(np.mean(arrival_errors_abs <= 1) * 100)
    within_2h_pct = float(np.mean(arrival_errors_abs <= 2) * 100)
    within_4h_pct = float(np.mean(arrival_errors_abs <= 4) * 100)
    within_8h_pct = float(np.mean(arrival_errors_abs <= 8) * 100)

    metrics = {
        "mean_arrival_error_hours": round(mean_error_hours, 2),
        "median_arrival_error_hours": round(median_error_hours, 2),
        "bias_hours": round(bias_hours, 2),
        "within_1h_pct": round(within_1h_pct, 2),
        "within_2h_pct": round(within_2h_pct, 2),
        "within_4h_pct": round(within_4h_pct, 2),
        "within_8h_pct": round(within_8h_pct, 2),
        "test_samples": int(len(arrival_errors_abs)),
    }

    logger.info(f"  Mean arrival error:    {metrics['mean_arrival_error_hours']} hours")
    logger.info(f"  Median arrival error:  {metrics['median_arrival_error_hours']} hours")
    logger.info(f"  Prediction bias:       {metrics['bias_hours']} hours (+ = late, - = early)")
    logger.info(f"  Within 1 hour:         {metrics['within_1h_pct']}%")
    logger.info(f"  Within 2 hours:        {metrics['within_2h_pct']}%")
    logger.info(f"  Within 4 hours:        {metrics['within_4h_pct']}%")
    logger.info(f"  Within 8 hours:        {metrics['within_8h_pct']}%")

    return metrics, arrival_errors_abs


def generate_validation_report(
    X_test,
    y_test,
    trip_start_test,
    ata_in_test,
    origin_test,
    destination_test,
    model,
    arrival_errors_abs
) -> pd.DataFrame:
    """
    Generate a CSV validation report with predicted vs actual arrivals.

    Returns DataFrame with columns:
    - trip_start
    - origin
    - destination
    - actual_arrival (ata_in)
    - predicted_arrival
    - error_hours
    - within_2h (boolean)
    """
    logger.info("Generating validation report...")

    # Predict durations
    predicted_duration_minutes = model.predict(X_test)

    # Calculate predicted arrivals
    predicted_arrivals = trip_start_test + pd.to_timedelta(predicted_duration_minutes, unit='m')

    # Build report DataFrame
    report_df = pd.DataFrame({
        'trip_start': trip_start_test.values,
        'origin': origin_test.values,
        'destination': destination_test.values,
        'actual_arrival_ata_in': ata_in_test.values,
        'predicted_arrival': predicted_arrivals.values,
        'predicted_duration_minutes': predicted_duration_minutes,
        'actual_duration_minutes': y_test.values,
        'error_hours': arrival_errors_abs,
        'within_2h': arrival_errors_abs <= 2,
        'within_1h': arrival_errors_abs <= 1,
    })

    # Sort by error (largest errors first for easy inspection)
    report_df = report_df.sort_values('error_hours', ascending=False)

    # Save to CSV
    report_df.to_csv(VALIDATION_REPORT_PATH, index=False)
    logger.info(f"Validation report saved to {VALIDATION_REPORT_PATH}")
    logger.info(f"  Total test samples: {len(report_df)}")
    logger.info(f"  Largest error: {report_df['error_hours'].max():.2f} hours")
    logger.info(f"  Smallest error: {report_df['error_hours'].min():.2f} hours")

    return report_df


def get_feature_importance(model, feature_names) -> dict:
    """Extract feature importance from the trained model."""
    importances = model.feature_importances_
    importance_dict = dict(zip(feature_names, [round(float(x), 4) for x in importances]))
    # Sort by importance
    return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))


def run_training():
    """Full training pipeline."""
    logger.info("=" * 60)
    logger.info("Starting ETA Model Training Pipeline")
    logger.info("=" * 60)

    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)

    try:
        # 1. Fetch data
        trips_df = fetch_training_data(conn)
        driver_stats = fetch_driver_stats(conn)
        route_stats = fetch_route_stats(conn)

        # 2. Clean data
        trips_df = clean_data(trips_df)

        # 3. Feature engineering
        logger.info("Engineering features...")
        featured_df = build_training_features(trips_df, driver_stats, route_stats)

        feature_cols = get_feature_columns()
        X = featured_df[feature_cols].astype(float)
        y = featured_df[TARGET_COLUMN].astype(float)

        logger.info(f"Feature matrix: {X.shape[0]} samples x {X.shape[1]} features")
        logger.info(f"Target range: {y.min():.0f} - {y.max():.0f} minutes")
        logger.info(f"Target median: {y.median():.0f} minutes ({y.median()/60:.1f} hours)")

        # 4. Train/test split - also split trip_start and ata_in using same indices
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Split the temporal columns using the same test indices
        trip_start_test = featured_df.loc[y_test.index, 'trip_start']
        ata_in_test = featured_df.loc[y_test.index, 'ata_in']
        origin_test = featured_df.loc[y_test.index, 'origin']
        destination_test = featured_df.loc[y_test.index, 'destination']

        logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")

        # 5. Train
        model = train_model(X_train, y_train)

        # 6. Evaluate - Duration metrics
        duration_metrics = evaluate_model(model, X_test, y_test.values)

        # 7. Evaluate - Arrival time accuracy
        arrival_metrics, arrival_errors_abs = evaluate_arrival_accuracy(
            model, X_test, trip_start_test, ata_in_test
        )

        # 8. Generate validation report CSV
        validation_report = generate_validation_report(
            X_test, y_test, trip_start_test, ata_in_test,
            origin_test, destination_test, model, arrival_errors_abs
        )

        # 9. Feature importance
        importance = get_feature_importance(model, feature_cols)
        logger.info("Feature Importance:")
        for feat, imp in importance.items():
            logger.info(f"  {feat:30s} {imp:.4f}")

        # 10. Save model
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        logger.info(f"Model saved to {MODEL_PATH}")

        # 11. Save metadata
        metadata = {
            "trained_at": datetime.now().isoformat(),
            "training_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "total_trips_used": int(len(featured_df)),
            "features": feature_cols,
            "target": TARGET_COLUMN,
            "model_type": "GradientBoostingRegressor",
            "hyperparameters": {
                "n_estimators": 300,
                "max_depth": 6,
                "learning_rate": 0.05,
                "subsample": 0.8,
            },
            "metrics": duration_metrics,
            "arrival_accuracy": arrival_metrics,
            "feature_importance": importance,
        }

        with open(METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata saved to {METADATA_PATH}")

        logger.info("=" * 60)
        logger.info("Training complete!")
        logger.info("=" * 60)

        return metadata

    finally:
        conn.close()


if __name__ == "__main__":
    run_training()