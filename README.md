Here's a complete, easy-to-understand breakdown of your Smart-Truck project:

---

## Smart-Truck Project Architecture & Flow

### What is Smart-Truck?

A **fleet management analytics platform** that takes raw trip CSV data (7.4 million rows), loads it into MySQL, runs 6 ML models on it, and presents insights through a React dashboard. It helps fleet managers track drivers, vehicles, routes, predict ETAs, detect anomalies, and recommend the best driver for a route.

---

### The 3 Services

| Service | Port | Tech | Role |
|---------|------|------|------|
| **Backend API** | 8000 | FastAPI + PyMySQL | Serves data from MySQL to frontend |
| **ML Service** | 8001 | FastAPI + Scikit-learn/XGBoost | Trains models, serves predictions |
| **Frontend** | 5173 | React 19 + TypeScript + Vite + Recharts | User interface |

---

### Source Data: What's in the CSV?

The main file is `trip_data.csv` (~7.4M rows). Key columns:

| Category | Columns | Purpose |
|----------|---------|---------|
| **Driver** | `s_driver_name`, `s_driver_mob1`, `s_driver_mob2` | Who drove |
| **Vehicle** | `s_asset_id`, `s_asset_type` | Which truck |
| **Route** | `s_origin`, `s_destination` | From where to where |
| **Customer** | `s_cnr_name`, `s_cne_name`, `i_cne_id` | Who booked |
| **Timestamps** | `dt_trip_start`, `dt_trip_end`, `dt_trip_eta`, `dt_ata_in` | When it happened |
| **Distance** | `i_trip_km`, `i_total_dist`, `i_cover_dist` | How far |
| **Status** | `c_trip_status`, `c_is_active`, `s_running_sts` | Trip state |
| **Business** | `s_dispatch_entry_no`, `s_invoice_no`, `s_material_desc` | Business info |

There are also **3 Waypoint Excel files** (`Waypoint_<VEHICLE_ID>.xls`) containing GPS tracking: DateTime, Latitude, Longitude, Speed, Distance, Status.

---

### Data Flow: CSV to Database

```
CSV (7.4M rows)
    │
    │  PASS 1: Extract unique dimensions
    ▼
┌─────────────────────────────────────────────┐
│  DIMENSION TABLES (deduplicated)            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ drivers  │ │ vehicles │ │locations │    │
│  │ ~780K    │ │ ~342K    │ │ ~21K     │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────┐                               │
│  │customers │                               │
│  │ ~5K      │                               │
│  └──────────┘                               │
└─────────────────────────────────────────────┘
    │
    │  PASS 2: Insert trips (linking to dimension IDs)
    │  + compute derived fields
    ▼
┌─────────────────────────────────────────────┐
│  TRIPS TABLE (7.4M rows)                    │
│  Computed fields:                           │
│  • trip_duration_minutes (end - start)      │
│  • eta_met (1 if arrived before ETA)        │
│  • eta_delay_minutes (how late)             │
│  • avg_speed_kmph (km / hours)              │
│  • eta_data_status ('available' or not)     │
│  • trip_km filled from route avg if missing │
└─────────────────────────────────────────────┘
    │
    │  PASS 3: Aggregate into summaries
    ▼
┌─────────────────────────────────────────────┐
│  SUMMARY TABLES (pre-computed analytics)    │
│  • driver_summary   (per driver KPIs)       │
│  • route_summary    (per route KPIs)        │
│  • vehicle_summary  (per vehicle KPIs)      │
│  • daily_fleet_stats (per day fleet-wide)   │
│  • route_time_patterns (per route+hour+day) │
└─────────────────────────────────────────────┘
```

**Key rule**: Only trips with `eta_data_status = 'available'` (i.e., they have an actual arrival time `dt_ata_in`) are used in summary tables. Trips without actual arrival data are stored but excluded from KPIs.

The migration code lives in two places:
- `migrations/migrate_data.py` - standalone CLI script
- `backend/app/services/data_migration.py` - called by the backend API
- `scripts/refresh_summaries.py` - delegates to migrate_data.py for summary refresh

---

### Summary Tables: What They Calculate

| Table | Groups by | Key Metrics |
|-------|-----------|-------------|
| **driver_summary** | driver_id | total_trips, eta_success_rate, avg_speed, avg_duration, vehicles_used, total_distance |
| **route_summary** | origin + destination | trip_count, avg_duration, avg_speed, eta_success_rate, avg_distance |
| **vehicle_summary** | vehicle_id | total_trips, drivers_used, avg_speed, eta_success_rate, total_distance |
| **daily_fleet_stats** | date | total_trips, total_distance, avg_speed, active_drivers, active_vehicles |
| **route_time_patterns** | route + hour + day_of_week | avg_duration, trip_count, eta_success_rate |

All summary queries filter with `WHERE t.eta_data_status = 'available' AND t.trip_duration_minutes > 0`.

---

### The 6 ML Models

#### Models WITH Frontend UI (4 tabs in ML Insights page):

| # | Model | Algorithm | What It Does | Input | Output |
|---|-------|-----------|-------------|-------|--------|
| 1 | **ETA Predictor** | XGBoost (300 trees) | Predicts how long a trip will take | Origin, Destination, Start Date, Driver ID, Vehicle ID | "Your trip ends April 9 at 8:00 AM" (arrival date/time) |
| 2 | **Anomaly Detector** | Isolation Forest | Flags suspicious/unusual trips | Trip duration, delay, ratios | "Anomaly Detected" or "Normal Trip" with score |
| 3 | **Driver Recommender** | Weighted Scoring | Ranks best drivers for a route | Origin, Destination, Top N | Ranked driver cards with score breakdown |
| 4 | **Trip Forecaster** | Ridge Regression + Exponential Smoothing | Predicts trips next 7 days | None (auto) | Fleet-wide chart + top route forecasts |

#### Models WITHOUT Frontend UI (backend-only, used via API):

| # | Model | Algorithm | What It Does | Used By |
|---|-------|-----------|-------------|---------|
| 5 | **Driver Scorer** | Weighted Formula | Scores every driver 0-100 | Driver list (Score column), Driver detail (score ring) |
| 6 | **Route Optimizer** | Dijkstra's + Gradient Boosting | Finds optimal route between locations | Available via API, no UI tab yet |

---

### How Each ML Model Works

**1. ETA Predictor** - "When will my truck arrive?"
- Trains on 500K trips from the trips table
- Uses 21 features: time of day, day of week, route history (avg duration, distance), driver history (avg speed, ETA compliance), vehicle stats, time-of-day patterns
- XGBoost vs LightGBM are compared; the better one is kept
- Frontend adds the trip start date to the predicted minutes to show an actual arrival date/time

**2. Anomaly Detector** - "Is this trip suspicious?"
- Trains on all trips using Isolation Forest (unsupervised - no labels needed)
- Uses 6 features: trip duration, ETA delay, duration ratio vs route average, delay ratio, hour deviation, night trip flag
- Scores each trip: negative = anomalous. Top 100 anomalies auto-generate alerts
- 5% contamination threshold (expects ~5% anomalies)

**3. Driver Scorer** - "How good is this driver?"
- Scores every driver with these weights:
  - ETA Compliance (40%): Do they arrive on time?
  - Speed Safety (20%): Are they in the optimal 35-55 km/h range?
  - Consistency (20%): How predictable are they?
  - Experience (10%): How many trips total?
  - Efficiency (10%): Distance covered per trip
  - Safety Penalty: -20 points for severe delays or excessive night driving
- Risk levels: Critical (<35), High (35-55), Medium (55-75), Low (75-100)
- Results stored in `predictions` table, displayed in driver list and detail pages

**4. Demand Forecaster / Trip Forecaster** - "How many trips next week?"
- Trains on daily trip counts grouped by route
- Uses 6 features: day index, day of week, month, weekend flag, 7-day moving avg, 14-day moving avg
- Ensemble: 60% Ridge Regression + 40% Exponential Smoothing
- Forecasts top 50 routes + fleet-wide totals for next 7 days

**5. Route Optimizer** - "What's the best path?"
- Builds a graph where locations are nodes and routes are edges (weighted by avg duration)
- Uses Dijkstra's algorithm to find shortest path (including multi-hop routes)
- Also trains a Gradient Boosting model for time-aware predictions (different estimate for Monday 8am vs Saturday 2pm)
- Identifies hub locations (high-traffic nodes)

**6. Driver Recommender** - "Who should I assign to this route?"
- Scores drivers using 5 weighted criteria:
  - Route Experience (25%): How many times they've done this exact route
  - ETA Compliance (30%): Their on-time delivery rate
  - Speed Efficiency (20%): Are they in the optimal speed range?
  - Consistency (15%): How predictable are their trip durations?
  - Overall Experience (10%): Total trips across all routes
- Falls back to overall stats if a driver hasn't done this specific route before

---

### Data Flow: Frontend → Backend → ML → Frontend

```
┌──────────────────────────────────────────────────────┐
│                    FRONTEND (React)                   │
│  Port 5173                                           │
│                                                       │
│  Pages: Dashboard, Drivers, Trips, Vehicles,          │
│         Routes, ML Insights, Migration                │
│                                                       │
│  Two Axios instances:                                 │
│  • backendApi → http://localhost:8000/api/v1          │
│  • mlApi      → http://localhost:8001                 │
└───────────┬──────────────────────┬────────────────────┘
            │                      │
   Backend calls              ML calls
            │                      │
            ▼                      ▼
┌───────────────────┐  ┌───────────────────────────────┐
│  BACKEND (FastAPI) │  │      ML SERVICE (FastAPI)     │
│  Port 8000         │  │      Port 8001                │
│                    │  │                               │
│  Endpoints:        │  │  Endpoints:                   │
│  /api/v1/drivers   │  │  /ml/predict/eta              │
│  /api/v1/trips     │  │  /ml/predict/anomaly          │
│  /api/v1/vehicles  │  │  /ml/drivers/scores           │
│  /api/v1/routes    │  │  /ml/recommend/drivers        │
│  /api/v1/dashboard │  │  /ml/forecast/trips           │
│  /api/v1/migrate   │  │  /ml/train-all                │
│                    │  │                               │
│  Uses: PyMySQL     │  │  Uses: joblib, sklearn,       │
│  DictCursor        │  │  XGBoost, numpy, pandas       │
│  Depends(get_db)   │  │                               │
└────────┬──────────┘  └────────┬──────────────────────┘
         │                      │
         │    Both query        │  Also loads .joblib
         │    MySQL             │  model files from disk
         ▼                      ▼
┌──────────────────────────────────────────────────────┐
│                 MySQL 8.0 (localhost:3306)            │
│                 Database: smart_truck                 │
│                                                       │
│  15 Tables:                                           │
│  ┌─────────────────────────────────────────┐         │
│  │ Dimension: drivers, vehicles, locations, │         │
│  │            customers                     │         │
│  ├─────────────────────────────────────────┤         │
│  │ Fact: trips, waypoints, file_uploads     │         │
│  ├─────────────────────────────────────────┤         │
│  │ Summary: driver_summary, route_summary,  │         │
│  │          vehicle_summary,                │         │
│  │          daily_fleet_stats,              │         │
│  │          route_time_patterns             │         │
│  ├─────────────────────────────────────────┤         │
│  │ ML: ml_models, predictions, alerts       │         │
│  └─────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────┘
```

---

### Example: ETA Prediction Flow (Step by Step)

1. **User** fills form on ML Insights page: Origin="Mumbai", Destination="Delhi", Start Date="2026-04-07 10:00"
2. **Frontend** sends `POST http://localhost:8001/ml/predict/eta` with form data
3. **ML Service** receives the request, opens a DB connection
4. **Feature Engineering** queries summary tables:
   - Route avg duration for Mumbai→Delhi from `route_summary`
   - Driver's avg speed & ETA rate from `driver_summary`
   - Vehicle stats from `vehicle_summary`
   - Time pattern for 10:00 AM on Monday from `route_time_patterns`
5. **Model Server** loads `eta_predictor.joblib` from disk (or memory cache)
6. **XGBoost** predicts: 2930 minutes
7. **ML Service** returns: `{ predicted_duration_minutes: 2930, route_avg_duration: 2800, ... }`
8. **Frontend** computes: April 7 10:00 AM + 2930 min = **April 9, 2026 at 6:50 PM**
9. **User sees**: "Your trip ends on Wednesday, April 9, 2026 at 6:50 PM" with a beautiful card

---

### Model Training Flow

```
POST /ml/train-all → runs in background
    │
    ├→ eta_predictor:    Query 500K trips → extract 21 features → train XGBoost → save .joblib
    ├→ anomaly_detector: Query 500K trips → extract 6 features → train IsolationForest → generate alerts
    ├→ driver_scorer:    Query driver_summary → compute weighted scores → save to predictions table
    ├→ demand_forecaster: Query daily trip counts → train Ridge + ExpSmoothing → forecast 7 days
    ├→ route_optimizer:  Build route graph → train Gradient Boosting → find optimal paths
    └→ driver_recommender: Query driver-route performance → compute composite scores → save artifact
    
Each model: saved as .joblib file + registered in ml_models table (versioned, is_active flag)
```

---

### Frontend Pages

| Page | URL | Data Source | What It Shows |
|------|-----|------------|---------------|
| Dashboard | `/` | Backend `/dashboard/*` | Fleet KPIs, daily trends, top drivers, alerts |
| Drivers | `/drivers` | Backend `/drivers` + ML `/drivers/scores` | Paginated list with ML Score column |
| Driver Detail | `/drivers/:id` | Backend `/drivers/:id` + ML `/drivers/:id/score` | Gaming profile card, charts, driving patterns |
| Trips | `/trips` | Backend `/trips` | Filterable trip list |
| Trip Detail | `/trips/:id` | Backend `/trips/:id` | Trip info + waypoint map |
| Routes | `/routes` | Backend `/routes` | Route list with stats |
| Route Detail | `/routes/:o/:d` | Backend `/routes/detail` | Route stats + time patterns |
| Vehicles | `/vehicles` | Backend `/vehicles` | Vehicle list |
| Vehicle Detail | `/vehicles/:id` | Backend `/vehicles/:id` | Vehicle stats + drivers |
| ML Insights | `/ml` | ML Service `/ml/*` | Model management + 4 prediction tabs |
| Migration | `/migration` | Backend `/migrate/*` | Data loading & progress tracking |

---

This covers the full architecture. The key thing to remember: **CSV → MySQL (dimensions + trips) → Summary tables → ML models train on summaries + trips → Predictions served via API → Frontend displays results**. The `eta_data_status` flag is the critical quality gate ensuring only complete trip data feeds into analytics and ML.
