from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import dashboard, drivers, trips, routes_analysis, vehicles, migrate

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

# API routes
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(drivers.router, prefix="/api/v1")
app.include_router(trips.router, prefix="/api/v1")
app.include_router(routes_analysis.router, prefix="/api/v1")
app.include_router(vehicles.router, prefix="/api/v1")
app.include_router(migrate.router, prefix="/api/v1")


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
