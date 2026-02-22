"""
FastAPI Backend for Trip Dispatch Analytics
Enhanced with pagination, filtering, and ETA prediction
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime, timedelta
import logging

try:
    from app.database import (
        get_health, get_data_summary, get_all_drivers, get_driver_summary,
        get_driver_trips, get_driver_vehicles, get_trip_overview,
        get_route_analysis, get_driver_performance_comparison,
        get_trips_paginated, get_trip_details, get_vehicles_paginated,
        get_vehicle_trips, predict_eta, get_route_stats, get_conn,
        get_all_locations, get_all_driver_names, get_trip_for_validation,
    )
    from app.ml.predict import predict_eta_ml, reload_model
except ImportError:
    from database import (
        get_health, get_data_summary, get_all_drivers, get_driver_summary,
        get_driver_trips, get_driver_vehicles, get_trip_overview,
        get_route_analysis, get_driver_performance_comparison,
        get_trips_paginated, get_trip_details, get_vehicles_paginated,
        get_vehicle_trips, predict_eta, get_route_stats, get_conn,
        get_all_locations, get_all_driver_names, get_trip_for_validation,
    )
    from ml.predict import predict_eta_ml, reload_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Trip Dispatch Analytics API",
    description="Comprehensive API for trip dispatch data analytics with pagination and predictions",
    version="3.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Trip Dispatch Analytics API",
        "version": "3.0.0",
        "backend": "PostgreSQL (Neon)",
        "features": [
            "Pagination",
            "Search & Filter",
            "ETA Prediction",
            "Driver Analytics",
            "Vehicle Tracking",
            "Route Analysis",
            "ML Prediction Validation"
        ]
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        return get_health()
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Database not available")


@app.get("/summary")
def data_summary():
    """Get data summary"""
    try:
        return get_data_summary()
    except Exception as e:
        logger.error(f"Error getting summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== DRIVER ENDPOINTS ==========

@app.get("/drivers")
def list_drivers(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None
):
    """Get paginated list of drivers with search"""
    try:
        return get_all_drivers(page=page, limit=limit, search=search)
    except Exception as e:
        logger.error(f"Error getting drivers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/driver/{driver_name}")
def get_driver(driver_name: str):
    """Get detailed analytics for a specific driver"""
    try:
        summary = get_driver_summary(driver_name)
        if "error" in summary:
            raise HTTPException(status_code=404, detail=summary["error"])
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver {driver_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/driver/{driver_name}/trips")
def get_driver_trip_list(
    driver_name: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get paginated trips for a specific driver"""
    try:
        return get_driver_trips(driver_name, page=page, limit=limit)
    except Exception as e:
        logger.error(f"Error getting trips for driver {driver_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/driver/{driver_name}/vehicles")
def get_driver_vehicle_list(driver_name: str):
    """Get all vehicles used by a specific driver"""
    try:
        return get_driver_vehicles(driver_name)
    except Exception as e:
        logger.error(f"Error getting vehicles for driver {driver_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== TRIP ENDPOINTS ==========

@app.get("/trips")
def list_trips(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    driver_name: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get paginated list of trips with filtering"""
    try:
        return get_trips_paginated(
            page=page,
            limit=limit,
            search=search,
            driver_name=driver_name,
            vehicle_id=vehicle_id,
            status=status,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        logger.error(f"Error getting trips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trip/{trip_id}")
def get_trip(trip_id: str):
    """Get detailed information for a specific trip"""
    try:
        trip = get_trip_details(trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        return trip
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trip {trip_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== VEHICLE ENDPOINTS ==========

@app.get("/vehicles")
def list_vehicles(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None
):
    """Get paginated list of vehicles with search"""
    try:
        return get_vehicles_paginated(page=page, limit=limit, search=search)
    except Exception as e:
        logger.error(f"Error getting vehicles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vehicle/{vehicle_id}/trips")
def get_vehicle_trip_list(
    vehicle_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get paginated trips for a specific vehicle"""
    try:
        return get_vehicle_trips(vehicle_id, page=page, limit=limit)
    except Exception as e:
        logger.error(f"Error getting trips for vehicle {vehicle_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== LOOKUP ENDPOINTS ==========

@app.get("/locations")
def list_locations():
    """Get all location names for dropdowns"""
    try:
        return get_all_locations()
    except Exception as e:
        logger.error(f"Error getting locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/driver-names")
def list_driver_names():
    """Get all driver names for dropdowns"""
    try:
        return get_all_driver_names()
    except Exception as e:
        logger.error(f"Error getting driver names: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== ANALYTICS ENDPOINTS ==========

@app.get("/overview")
def trip_overview():
    """Get overall trip statistics"""
    try:
        return get_trip_overview()
    except Exception as e:
        logger.error(f"Error getting overview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/routes")
def route_analysis(limit: int = Query(20, ge=1, le=100)):
    """Get route analysis"""
    try:
        return get_route_analysis(limit=limit)
    except Exception as e:
        logger.error(f"Error getting routes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/top-performers")
def top_performers(limit: int = Query(10, ge=1, le=50)):
    """Get top performing drivers"""
    try:
        return get_driver_performance_comparison(limit)
    except Exception as e:
        logger.error(f"Error getting top performers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-eta")
def predict_trip_eta(
    origin: str,
    destination: str,
    driver_name: Optional[str] = None,
    vehicle_id: Optional[str] = None
):
    """Predict ETA for a trip based on historical averages (legacy)"""
    try:
        return predict_eta(origin, destination, driver_name, vehicle_id)
    except Exception as e:
        logger.error(f"Error predicting ETA: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-eta-ml")
def predict_trip_eta_ml(
    origin: str,
    destination: str,
    trip_start: str,
    driver_name: Optional[str] = None,
):
    """Predict ETA using ML regression model based on driver patterns and route history"""
    try:
        conn = get_conn()
        result = predict_eta_ml(conn, origin, destination, trip_start, driver_name)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error in ML ETA prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrain-model")
def retrain_model():
    """Retrain the ML model with latest data"""
    try:
        try:
            from app.ml.train import run_training
        except ImportError:
            from ml.train import run_training
        metadata = run_training()
        reload_model()
        return {
            "status": "success",
            "message": "Model retrained successfully",
            "metrics": metadata.get("metrics"),
            "arrival_accuracy": metadata.get("arrival_accuracy"),
            "trained_at": metadata.get("trained_at"),
            "training_samples": metadata.get("training_samples"),
        }
    except Exception as e:
        logger.error(f"Error retraining model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/route-stats/{origin}/{destination}")
def get_route_statistics(origin: str, destination: str):
    """Get detailed statistics for a specific route"""
    try:
        return get_route_stats(origin, destination)
    except Exception as e:
        logger.error(f"Error getting route stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== NEW: VALIDATION ENDPOINT ==========

@app.get("/validate-prediction/{trip_id}")
async def validate_prediction(trip_id: int):
    """
    Validate ML prediction against actual arrival for a completed trip.

    Compare the ML model's prediction with what actually happened for a specific trip.
    This helps assess model accuracy and identify areas for improvement.

    Parameters:
        trip_id: The dispatch_entry_no of a completed trip

    Returns:
        Detailed comparison of predicted vs actual arrival time with error metrics
    """
    try:
        # Fetch the trip details
        trip = get_trip_for_validation(trip_id)

        if not trip:
            raise HTTPException(
                status_code=404,
                detail=f"Trip {trip_id} not found or not completed (needs ata_in)"
            )

        # Extract trip details
        trip_start_str = trip['trip_start'].isoformat()
        origin = trip['origin']
        destination = trip['destination']
        driver_name = trip.get('driver_name')
        actual_arrival = trip['ata_in']
        actual_duration_minutes = float(trip['trip_duration_minutes'])

        # Make ML prediction using the trip's original parameters
        conn = get_conn()
        prediction = predict_eta_ml(
            conn=conn,
            origin=origin,
            destination=destination,
            trip_start_str=trip_start_str,
            driver_name=driver_name
        )

        if not prediction.get('prediction_available'):
            raise HTTPException(
                status_code=400,
                detail=prediction.get('message', 'Prediction not available for this route')
            )

        # Parse predicted arrival
        predicted_arrival = datetime.fromisoformat(prediction['predicted_arrival'])
        predicted_duration_minutes = prediction['predicted_duration_minutes']

        # Calculate errors
        arrival_error_seconds = abs((predicted_arrival - actual_arrival).total_seconds())
        arrival_error_hours = arrival_error_seconds / 3600
        arrival_error_minutes = arrival_error_seconds / 60

        duration_error_minutes = abs(predicted_duration_minutes - actual_duration_minutes)

        # Determine if prediction was good
        within_1h = arrival_error_hours <= 1
        within_2h = arrival_error_hours <= 2
        within_4h = arrival_error_hours <= 4

        # Build response
        response = {
            "trip_id": trip_id,
            "trip_details": {
                "origin": origin,
                "destination": destination,
                "driver_name": driver_name,
                "vehicle_no": trip.get('vehicle_no'),
                "trip_start": trip_start_str,
                "actual_arrival": actual_arrival.isoformat(),
                "actual_duration_minutes": actual_duration_minutes,
                "actual_duration_hours": round(actual_duration_minutes / 60, 2),
                "distance_km": float(trip['trip_km']) if trip['trip_km'] else None,
                "eta_met_originally": trip['eta_met'],
            },
            "ml_prediction": {
                "predicted_arrival": prediction['predicted_arrival'],
                "predicted_duration_minutes": predicted_duration_minutes,
                "predicted_duration_hours": prediction['predicted_duration_hours'],
                "confidence": prediction['confidence'],
                "model_type": prediction['model_type'],
            },
            "validation_results": {
                "arrival_error_hours": round(arrival_error_hours, 2),
                "arrival_error_minutes": round(arrival_error_minutes, 2),
                "duration_error_minutes": round(duration_error_minutes, 2),
                "within_1_hour": within_1h,
                "within_2_hours": within_2h,
                "within_4_hours": within_4h,
                "prediction_quality": (
                    "excellent" if within_1h else
                    "good" if within_2h else
                    "acceptable" if within_4h else
                    "poor"
                ),
            },
            "comparison": {
                "predicted_vs_actual_arrival": {
                    "predicted": prediction['predicted_arrival'],
                    "actual": actual_arrival.isoformat(),
                    "difference": f"{'+' if (predicted_arrival > actual_arrival) else ''}{round((predicted_arrival - actual_arrival).total_seconds() / 3600, 2)} hours"
                },
                "predicted_vs_actual_duration": {
                    "predicted_minutes": predicted_duration_minutes,
                    "actual_minutes": actual_duration_minutes,
                    "difference_minutes": round(predicted_duration_minutes - actual_duration_minutes, 2)
                }
            }
        }

        # Add route and driver historical data if available
        if 'route_historical_avg_minutes' in prediction:
            response['historical_context'] = {
                "route_avg_duration_minutes": prediction['route_historical_avg_minutes'],
                "route_trip_count": prediction['route_trip_count'],
            }

            if driver_name and 'driver_avg_duration_minutes' in prediction:
                response['historical_context']['driver_avg_duration_minutes'] = prediction['driver_avg_duration_minutes']
                response['historical_context']['driver_eta_success_rate'] = prediction['driver_eta_success_rate']

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating prediction for trip {trip_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)