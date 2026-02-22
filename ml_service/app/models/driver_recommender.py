"""
Model 7: Driver Recommender
- Replaces the LSTM predictor
- Given a route (origin + destination), ranks all available drivers based on
  their historical performance on that route and similar routes
- Scoring criteria: avg speed, ETA compliance, consistency, experience on route
- Output: ranked list of top N drivers with scores and reasoning
"""

import logging
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import joblib

logger = logging.getLogger(__name__)


def fetch_driver_route_performance(conn) -> pd.DataFrame:
    """Get per-driver per-route performance stats."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                t.driver_id,
                d.name AS driver_name,
                d.mobile1 AS driver_mobile,
                lo.name AS origin,
                ld.name AS destination,
                COUNT(*) AS route_trips,
                ROUND(AVG(t.trip_duration_minutes), 2) AS avg_duration_min,
                ROUND(AVG(t.avg_speed_kmph), 2) AS avg_speed_kmph,
                ROUND(AVG(t.trip_km), 2) AS avg_distance_km,
                ROUND(SUM(CASE WHEN t.eta_met = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS eta_success_rate,
                ROUND(AVG(t.eta_delay_minutes), 2) AS avg_delay_min,
                ROUND(STDDEV(t.trip_duration_minutes), 2) AS duration_stddev
            FROM trips t
            JOIN drivers d ON t.driver_id = d.id
            JOIN locations lo ON t.origin_id = lo.id
            JOIN locations ld ON t.destination_id = ld.id
            WHERE t.trip_duration_minutes IS NOT NULL
              AND t.trip_duration_minutes > 0
              AND t.eta_data_status = 'available'
              AND t.driver_id IS NOT NULL
            GROUP BY t.driver_id, d.name, d.mobile1, lo.name, ld.name
            HAVING COUNT(*) >= 1
        """)
        rows = cur.fetchall()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_driver_overall_stats(conn) -> pd.DataFrame:
    """Get overall driver performance from driver_summary."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                driver_id,
                driver_name,
                total_trips,
                eta_success_rate,
                avg_speed_kmph,
                avg_duration_min,
                avg_distance_km,
                avg_eta_delay_min,
                vehicles_used
            FROM driver_summary
            WHERE total_trips >= 2
        """)
        rows = cur.fetchall()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def train(conn, models_dir: Path) -> dict:
    logger.info("=" * 50)
    logger.info("TRAINING: Driver Recommender")
    logger.info("=" * 50)

    route_perf = fetch_driver_route_performance(conn)
    overall_stats = fetch_driver_overall_stats(conn)

    if route_perf.empty:
        logger.error("No driver-route performance data available")
        return {"error": "No driver-route performance data"}

    if overall_stats.empty:
        logger.error("No driver summary data available")
        return {"error": "No driver summary data"}

    # Convert Decimal types
    for col in route_perf.select_dtypes(include=["object"]).columns:
        try:
            route_perf[col] = pd.to_numeric(route_perf[col], errors="ignore")
        except Exception:
            pass

    for col in overall_stats.select_dtypes(include=["object"]).columns:
        try:
            overall_stats[col] = pd.to_numeric(overall_stats[col], errors="ignore")
        except Exception:
            pass

    unique_routes = route_perf.groupby(["origin", "destination"]).size().reset_index(name="driver_count")
    unique_drivers = route_perf["driver_id"].nunique()

    logger.info(f"Driver-route data: {len(route_perf):,} records")
    logger.info(f"Unique routes with driver data: {len(unique_routes):,}")
    logger.info(f"Unique drivers: {unique_drivers:,}")
    logger.info(f"Overall driver stats: {len(overall_stats):,} drivers")

    # Compute global averages for normalization
    global_avg_speed = float(overall_stats["avg_speed_kmph"].mean()) or 40.0
    global_avg_eta_success = float(overall_stats["eta_success_rate"].mean()) or 50.0

    # Save model artifact
    model_path = str(models_dir / "driver_recommender.joblib")
    joblib.dump({
        "route_performance": route_perf.to_dict("records"),
        "overall_stats": overall_stats.to_dict("records"),
        "global_avg_speed": global_avg_speed,
        "global_avg_eta_success": global_avg_eta_success,
        "generated_at": datetime.now().isoformat(),
    }, model_path)

    # Register model in DB
    with conn.cursor() as cur:
        cur.execute("UPDATE ml_models SET is_active = 0 WHERE model_name = 'driver_recommender'")
        cur.execute("SELECT COALESCE(MAX(version), 0) AS max_v FROM ml_models WHERE model_name = 'driver_recommender'")
        version = cur.fetchone()["max_v"] + 1

        metrics_json = json.dumps({
            "unique_routes": len(unique_routes),
            "unique_drivers": int(unique_drivers),
            "driver_route_records": len(route_perf),
            "global_avg_speed": round(global_avg_speed, 2),
            "global_avg_eta_success": round(global_avg_eta_success, 2),
        })

        cur.execute("""
            INSERT INTO ml_models (model_name, version, model_type, target_variable, metrics,
                                   feature_columns, model_artifact_path, training_data_count, is_active)
            VALUES ('driver_recommender', %s, 'ranking_scoring', 'driver_rank', %s, %s, %s, %s, 1)
        """, (
            version,
            metrics_json,
            json.dumps(["eta_success_rate", "avg_speed_kmph", "consistency", "route_experience"]),
            model_path,
            len(route_perf),
        ))
    conn.commit()

    logger.info(f"Driver recommender saved to {model_path}")

    return {
        "unique_routes": len(unique_routes),
        "unique_drivers": int(unique_drivers),
        "driver_route_records": len(route_perf),
        "model_path": model_path,
    }


def recommend_drivers(artifact: dict, origin: str, destination: str, top_n: int = 10) -> dict:
    """
    Recommend best drivers for a given route based on historical performance.
    Scores drivers on: route experience, speed, ETA compliance, consistency.
    Falls back to overall stats if driver hasn't done this exact route.
    """
    route_perf = pd.DataFrame(artifact["route_performance"])
    overall_stats = pd.DataFrame(artifact["overall_stats"])
    global_avg_speed = artifact.get("global_avg_speed", 40.0)
    global_avg_eta_success = artifact.get("global_avg_eta_success", 50.0)

    if route_perf.empty and overall_stats.empty:
        return {"error": "No driver data available"}

    # Convert Decimal types
    for col in route_perf.columns:
        route_perf[col] = pd.to_numeric(route_perf[col], errors="ignore")
    for col in overall_stats.columns:
        overall_stats[col] = pd.to_numeric(overall_stats[col], errors="ignore")

    # Drivers with experience on this exact route
    route_drivers = route_perf[
        (route_perf["origin"] == origin) & (route_perf["destination"] == destination)
    ].copy()

    # Get overall stats for all drivers
    if overall_stats.empty:
        return {"error": "No driver summary data"}

    # Score each driver in overall_stats
    all_drivers = overall_stats.copy()

    # Merge route-specific data where available
    if not route_drivers.empty:
        route_driver_dict = route_drivers.set_index("driver_id").to_dict("index")
    else:
        route_driver_dict = {}

    scored_drivers = []
    for _, driver in all_drivers.iterrows():
        did = int(driver["driver_id"])
        route_data = route_driver_dict.get(did, None)

        # 1. Route Experience Score (25% weight)
        if route_data:
            route_trips = float(route_data.get("route_trips", 0))
            route_exp_score = min(100, route_trips * 15)  # 7+ trips on route = 100
        else:
            route_exp_score = 0

        # 2. ETA Compliance Score (30% weight)
        if route_data:
            eta_rate = float(route_data.get("eta_success_rate", 0))
        else:
            eta_rate = float(driver.get("eta_success_rate", 0))
        eta_score = min(100, eta_rate)

        # 3. Speed Efficiency Score (20% weight)
        if route_data and route_data.get("avg_speed_kmph"):
            speed = float(route_data.get("avg_speed_kmph", 0))
        else:
            speed = float(driver.get("avg_speed_kmph", 0))
        # Optimal speed range for trucks: 35-55 km/h
        if 35 <= speed <= 55:
            speed_score = 100
        elif speed > 0:
            speed_score = max(0, 100 - abs(speed - 45) * 3)
        else:
            speed_score = 0

        # 4. Consistency Score (15% weight)
        if route_data and route_data.get("duration_stddev"):
            stddev = float(route_data.get("duration_stddev", 0))
            if stddev == 0:
                consistency_score = 100
            else:
                avg_dur = float(route_data.get("avg_duration_min", 1))
                cv = stddev / max(avg_dur, 1)  # coefficient of variation
                consistency_score = max(0, 100 - cv * 100)
        else:
            consistency_score = 50  # neutral if no route data

        # 5. Overall Experience Score (10% weight)
        total_trips = float(driver.get("total_trips", 0))
        exp_score = min(100, np.log1p(total_trips) / np.log1p(100) * 100)

        # Composite score
        composite = (
            route_exp_score * 0.25 +
            eta_score * 0.30 +
            speed_score * 0.20 +
            consistency_score * 0.15 +
            exp_score * 0.10
        )

        scored_drivers.append({
            "driver_id": did,
            "driver_name": str(driver.get("driver_name", "Unknown")),
            "composite_score": round(composite, 2),
            "route_experience_score": round(route_exp_score, 2),
            "eta_compliance_score": round(eta_score, 2),
            "speed_efficiency_score": round(speed_score, 2),
            "consistency_score": round(consistency_score, 2),
            "overall_experience_score": round(exp_score, 2),
            "has_route_experience": route_data is not None,
            "route_trips": int(route_data["route_trips"]) if route_data else 0,
            "avg_speed_kmph": round(float(route_data["avg_speed_kmph"]) if route_data and route_data.get("avg_speed_kmph") else float(driver.get("avg_speed_kmph", 0)), 2),
            "eta_success_rate": round(float(route_data["eta_success_rate"]) if route_data else float(driver.get("eta_success_rate", 0)), 2),
            "total_trips": int(total_trips),
        })

    # Sort by composite score descending
    scored_drivers.sort(key=lambda x: x["composite_score"], reverse=True)

    # Take top N
    top_drivers = scored_drivers[:top_n]

    return {
        "origin": origin,
        "destination": destination,
        "total_candidates": len(scored_drivers),
        "drivers_with_route_exp": sum(1 for d in scored_drivers if d["has_route_experience"]),
        "recommended_drivers": top_drivers,
    }
