-- ============================================
-- Trip Dispatch Analytics - Database Schema
-- Target: Neon PostgreSQL (Serverless)
-- ============================================

-- Drop existing objects if re-running
DROP MATERIALIZED VIEW IF EXISTS mv_route_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_driver_summary CASCADE;
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS vehicles CASCADE;
DROP TABLE IF EXISTS drivers CASCADE;

-- ============================================
-- DIMENSION TABLES
-- ============================================

-- Drivers
CREATE TABLE drivers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    mobile1 TEXT,
    mobile2 TEXT,
    UNIQUE(name, mobile1)
);

-- Vehicles
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
    asset_id TEXT NOT NULL UNIQUE,
    asset_type TEXT,
    trailer_type TEXT
);

-- Locations (origins + destinations deduplicated)
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- Customers
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    cne_name TEXT,
    cne_id INTEGER,
    cust_login_id TEXT,
    UNIQUE(cust_login_id)
);

-- ============================================
-- FACT TABLE
-- ============================================

CREATE TABLE trips (
    id SERIAL PRIMARY KEY,
    dispatch_entry_no TEXT NOT NULL UNIQUE,

    -- Foreign keys
    driver_id INTEGER REFERENCES drivers(id),
    vehicle_id INTEGER REFERENCES vehicles(id),
    origin_id INTEGER REFERENCES locations(id),
    destination_id INTEGER REFERENCES locations(id),
    customer_id INTEGER REFERENCES customers(id),

    -- Timestamps
    trip_start TIMESTAMP,
    trip_end TIMESTAMP,
    trip_eta TIMESTAMP,
    ata_in TIMESTAMP,
    ata_out TIMESTAMP,
    dt_created TIMESTAMP,
    dt_updated TIMESTAMP,

    -- Distances
    trip_km NUMERIC(10,2),
    total_dist NUMERIC(10,2),
    cover_dist NUMERIC(10,2),

    -- Pre-computed analytics fields
    trip_duration_minutes NUMERIC(12,2),
    eta_met BOOLEAN,
    eta_delay_minutes NUMERIC(12,2),
    avg_speed_kmph NUMERIC(8,2),

    -- Business fields
    trip_status TEXT,
    is_active TEXT,
    trip_close_remark TEXT,
    material_desc TEXT,
    invoice_no TEXT,
    invoice_date TEXT,
    ref_no TEXT,
    ref_date TEXT,
    entry_type TEXT,
    own_market_type TEXT,
    running_sts TEXT,
    trip_seq INTEGER,
    delay_by NUMERIC(10,2),

    -- Device info
    device_id TEXT,
    device_type TEXT,

    -- Metadata
    entity_id INTEGER,
    cnr_id INTEGER,
    created_by TEXT,
    updated_by TEXT,
    track_link TEXT,
    data_string TEXT
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX idx_trips_driver_id ON trips(driver_id);
CREATE INDEX idx_trips_origin_dest ON trips(origin_id, destination_id);
CREATE INDEX idx_trips_eta_met ON trips(eta_met);
CREATE INDEX idx_trips_trip_start ON trips(trip_start);
CREATE INDEX idx_trips_status ON trips(trip_status);

-- ============================================
-- MATERIALIZED VIEWS
-- ============================================

-- Driver performance summary
CREATE MATERIALIZED VIEW mv_driver_summary AS
SELECT
    d.id AS driver_id,
    d.name AS driver_name,
    d.mobile1 AS driver_mobile,
    COUNT(*) AS total_trips,
    SUM(CASE WHEN t.eta_met THEN 1 ELSE 0 END) AS eta_met_count,
    ROUND(
        SUM(CASE WHEN t.eta_met THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2
    ) AS eta_success_rate,
    ROUND(AVG(t.trip_duration_minutes), 2) AS avg_duration_min,
    ROUND(MAX(t.trip_duration_minutes), 2) AS max_duration_min,
    ROUND(MIN(t.trip_duration_minutes), 2) AS min_duration_min,
    ROUND(AVG(t.avg_speed_kmph), 2) AS avg_speed_kmph,
    COUNT(DISTINCT t.vehicle_id) AS vehicles_used,
    ROUND(SUM(t.trip_km), 2) AS total_distance_km,
    ROUND(AVG(t.trip_km), 2) AS avg_distance_km,
    ROUND(AVG(t.eta_delay_minutes), 2) AS avg_eta_delay_min
FROM trips t
JOIN drivers d ON t.driver_id = d.id
GROUP BY d.id, d.name, d.mobile1;

CREATE UNIQUE INDEX idx_mv_driver_summary_id ON mv_driver_summary(driver_id);

-- Route performance summary
CREATE MATERIALIZED VIEW mv_route_summary AS
SELECT
    lo.name AS origin,
    ld.name AS destination,
    lo.name || ' → ' || ld.name AS route,
    COUNT(*) AS trip_count,
    ROUND(AVG(t.trip_duration_minutes), 2) AS avg_duration_min,
    ROUND(
        SUM(CASE WHEN t.eta_met THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2
    ) AS eta_success_rate,
    ROUND(AVG(t.trip_km), 2) AS avg_distance_km
FROM trips t
JOIN locations lo ON t.origin_id = lo.id
JOIN locations ld ON t.destination_id = ld.id
GROUP BY lo.name, ld.name
ORDER BY trip_count DESC;
