"""
Feature Engineering for ETA Prediction Model

Extracts and transforms raw trip data into ML-ready features.
Shared between training (train.py) and prediction (predict.py).
"""

import pandas as pd
import numpy as np
from datetime import datetime


def extract_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract time-based features from trip_start timestamp."""
    df = df.copy()
    df["hour_of_day"] = df["trip_start"].dt.hour
    df["day_of_week"] = df["trip_start"].dt.dayofweek  # 0=Monday, 6=Sunday
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["month"] = df["trip_start"].dt.month

    # Time-of-day buckets: night(0-6), morning(6-12), afternoon(12-18), evening(18-24)
    df["time_bucket"] = pd.cut(
        df["hour_of_day"],
        bins=[-1, 6, 12, 18, 24],
        labels=[0, 1, 2, 3]  # night, morning, afternoon, evening
    ).astype(int)

    return df


def build_training_features(df: pd.DataFrame, driver_stats: pd.DataFrame, route_stats: pd.DataFrame) -> pd.DataFrame:
    """
    Build the full feature set for training.

    Parameters:
        df: Raw trip data with columns:
            trip_start, trip_duration_minutes, origin, destination,
            driver_id, trip_km, avg_speed_kmph
        driver_stats: Pre-aggregated driver stats from mv_driver_summary
        route_stats: Pre-aggregated route stats from mv_route_summary

    Returns:
        DataFrame with all features + target column (trip_duration_minutes)
    """
    df = df.copy()

    # --- 1. Temporal features ---
    df = extract_temporal_features(df)

    # --- 2. Route-level features (merge from route_stats) ---
    df = df.merge(
        route_stats[["origin", "destination", "route_avg_duration", "route_avg_distance", "route_trip_count", "route_eta_success_rate"]],
        on=["origin", "destination"],
        how="left"
    )

    # --- 3. Driver-level features (merge from driver_stats) ---
    if "driver_id" in df.columns:
        df = df.merge(
            driver_stats[["driver_id", "driver_avg_duration", "driver_avg_speed", "driver_eta_success_rate", "driver_total_trips", "driver_avg_distance"]],
            on="driver_id",
            how="left"
        )

    # --- 4. Fill NaN for missing driver/route data ---
    global_avg_duration = df["trip_duration_minutes"].median()
    global_avg_speed = df["avg_speed_kmph"].median()
    global_avg_distance = df["trip_km"].median() if "trip_km" in df.columns else 0

    driver_fill = {
        "driver_avg_duration": global_avg_duration,
        "driver_avg_speed": global_avg_speed if pd.notna(global_avg_speed) else 20.0,
        "driver_eta_success_rate": 50.0,
        "driver_total_trips": 0,
        "driver_avg_distance": global_avg_distance if pd.notna(global_avg_distance) else 0,
    }
    df.fillna(driver_fill, inplace=True)

    route_fill = {
        "route_avg_duration": global_avg_duration,
        "route_avg_distance": global_avg_distance if pd.notna(global_avg_distance) else 0,
        "route_trip_count": 0,
        "route_eta_success_rate": 50.0,
    }
    df.fillna(route_fill, inplace=True)

    # --- 5. Trip distance feature ---
    df["distance_km"] = df["trip_km"].fillna(df["route_avg_distance"])

    # --- 6. Interaction / derived features ---

    # How does this driver compare to the route average? (driver deviation)
    # ratio > 1 means driver is slower than route avg, < 1 means faster
    df["driver_vs_route_duration_ratio"] = np.where(
        df["route_avg_duration"] > 0,
        df["driver_avg_duration"] / df["route_avg_duration"],
        1.0
    )

    # Estimated duration from speed: distance / speed * 60 (convert hrs to mins)
    df["speed_estimated_duration"] = np.where(
        df["driver_avg_speed"] > 0,
        (df["distance_km"] / df["driver_avg_speed"]) * 60,
        df["route_avg_duration"]
    )

    # Driver experience level (log transform to reduce skew)
    df["driver_experience_log"] = np.log1p(df["driver_total_trips"])

    # Route popularity (log transform)
    df["route_popularity_log"] = np.log1p(df["route_trip_count"])

    # Has driver data? (binary flag — model can learn to weight differently)
    if "driver_id" in df.columns:
        df["has_driver"] = df["driver_id"].notna().astype(int)
    else:
        df["has_driver"] = 0

    return df


def get_feature_columns():
    """Return the list of feature columns used by the model."""
    return [
        # Temporal
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "month",
        "time_bucket",
        # Route aggregate
        "route_avg_duration",
        "route_avg_distance",
        "route_trip_count",
        "route_eta_success_rate",
        # Driver aggregate
        "driver_avg_duration",
        "driver_avg_speed",
        "driver_eta_success_rate",
        "driver_total_trips",
        "driver_avg_distance",
        # Trip-level
        "distance_km",
        # Interaction / derived
        "driver_vs_route_duration_ratio",
        "speed_estimated_duration",
        "driver_experience_log",
        "route_popularity_log",
        "has_driver",
    ]


TARGET_COLUMN = "trip_duration_minutes"


def prepare_prediction_features(
    origin: str,
    destination: str,
    trip_start: datetime,
    driver_id: int = None,
    driver_stats_row: dict = None,
    route_stats_row: dict = None,
    trip_km: float = None,
) -> pd.DataFrame:
    """
    Build a single-row feature DataFrame for prediction at inference time.
    """
    row = {}

    # --- Temporal ---
    row["hour_of_day"] = trip_start.hour
    row["day_of_week"] = trip_start.weekday()
    row["is_weekend"] = 1 if trip_start.weekday() >= 5 else 0
    row["month"] = trip_start.month

    hour = trip_start.hour
    if hour <= 6:
        row["time_bucket"] = 0
    elif hour <= 12:
        row["time_bucket"] = 1
    elif hour <= 18:
        row["time_bucket"] = 2
    else:
        row["time_bucket"] = 3

    # --- Route stats ---
    if route_stats_row:
        row["route_avg_duration"] = float(route_stats_row.get("avg_duration_min", 0) or 0)
        row["route_avg_distance"] = float(route_stats_row.get("avg_distance_km", 0) or 0)
        row["route_trip_count"] = int(route_stats_row.get("trip_count", 0) or 0)
        row["route_eta_success_rate"] = float(route_stats_row.get("eta_success_rate", 50) or 50)
    else:
        row["route_avg_duration"] = 0
        row["route_avg_distance"] = 0
        row["route_trip_count"] = 0
        row["route_eta_success_rate"] = 50.0

    # --- Driver stats ---
    if driver_stats_row:
        row["driver_avg_duration"] = float(driver_stats_row.get("avg_duration_min", 0) or 0)
        row["driver_avg_speed"] = float(driver_stats_row.get("avg_speed_kmph", 0) or 0)
        row["driver_eta_success_rate"] = float(driver_stats_row.get("eta_success_rate", 50) or 50)
        row["driver_total_trips"] = int(driver_stats_row.get("total_trips", 0) or 0)
        row["driver_avg_distance"] = float(driver_stats_row.get("avg_distance_km", 0) or 0)
        row["has_driver"] = 1
    else:
        row["driver_avg_duration"] = 0
        row["driver_avg_speed"] = 0
        row["driver_eta_success_rate"] = 50.0
        row["driver_total_trips"] = 0
        row["driver_avg_distance"] = 0
        row["has_driver"] = 0

    # --- Distance ---
    if trip_km is not None:
        row["distance_km"] = trip_km
    else:
        row["distance_km"] = row["route_avg_distance"]

    # --- Interaction / derived features ---
    # Driver vs route duration ratio
    if row["route_avg_duration"] > 0 and row["driver_avg_duration"] > 0:
        row["driver_vs_route_duration_ratio"] = row["driver_avg_duration"] / row["route_avg_duration"]
    else:
        row["driver_vs_route_duration_ratio"] = 1.0

    # Speed-estimated duration
    if row["driver_avg_speed"] > 0:
        row["speed_estimated_duration"] = (row["distance_km"] / row["driver_avg_speed"]) * 60
    else:
        row["speed_estimated_duration"] = row["route_avg_duration"]

    # Log transforms
    row["driver_experience_log"] = np.log1p(row["driver_total_trips"])
    row["route_popularity_log"] = np.log1p(row["route_trip_count"])

    df = pd.DataFrame([row])
    return df[get_feature_columns()]
