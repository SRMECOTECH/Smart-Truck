import time
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config.logging_config import setup_logging
from backend.app.api import dashboard, drivers, trips, routes_analysis, vehicles, migrate, locations

# --- Logging ---
setup_logging(service_name="backend")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Smart-Truck API",
    description="Fleet management platform - Backend API",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request logging middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    logger.info(">>> %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("!!! %s %s  UNHANDLED EXCEPTION", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "<<< %s %s  %s  %.0fms",
        request.method, request.url.path, response.status_code, elapsed_ms,
    )
    return response


# API routes
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(drivers.router, prefix="/api/v1")
app.include_router(trips.router, prefix="/api/v1")
app.include_router(routes_analysis.router, prefix="/api/v1")
app.include_router(vehicles.router, prefix="/api/v1")
app.include_router(migrate.router, prefix="/api/v1")
app.include_router(locations.router)

logger.info("Backend API ready  routes=%d", len(app.routes))


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "smart-truck-api"}


@app.get("/api/v1")
def api_root():
    return {
        "message": "Smart-Truck API v1",
        "docs": "/docs",
        "endpoints": {
            "dashboard": "/api/v1/dashboard/summary",
            "drivers": "/api/v1/drivers",
            "trips": "/api/v1/trips",
            "routes": "/api/v1/routes",
            "vehicles": "/api/v1/vehicles",
            "migration": {
                "create_schema": "POST /api/v1/migrate/schema",
                "migrate_trips": "POST /api/v1/migrate/trips",
                "migrate_waypoints": "POST /api/v1/migrate/waypoints",
                "refresh_summaries": "POST /api/v1/migrate/refresh-summaries",
                "check_status": "GET /api/v1/migrate/status",
            },
        },
    }
