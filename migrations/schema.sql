-- ============================================
-- Smart-Truck: MySQL Database Schema
-- Target: MySQL 8.0 (Local Development)
-- ============================================

USE smart_truck;

-- ============================================
-- DIMENSION TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS drivers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    mobile1 VARCHAR(20),
    mobile2 VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_driver_name_mobile (name, mobile1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id VARCHAR(50) NOT NULL UNIQUE,
    asset_type VARCHAR(100),
    trailer_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cne_name VARCHAR(255),
    cne_id INT,
    cust_login_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customer_login (cust_login_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- FACT TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS trips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dispatch_entry_no VARCHAR(100) NOT NULL UNIQUE,

    -- Foreign keys
    driver_id INT,
    vehicle_id INT,
    origin_id INT,
    destination_id INT,
    customer_id INT,

    -- Timestamps
    trip_start DATETIME,
    trip_end DATETIME,
    trip_eta DATETIME,
    ata_in DATETIME,
    ata_out DATETIME,
    dt_created DATETIME,
    dt_updated DATETIME,

    -- Distances
    trip_km DECIMAL(10,2),
    total_dist DECIMAL(10,2),
    cover_dist DECIMAL(10,2),

    -- Pre-computed analytics
    trip_duration_minutes DECIMAL(12,2),
    eta_met TINYINT(1),
    eta_delay_minutes DECIMAL(12,2),
    avg_speed_kmph DECIMAL(8,2),

    -- Data quality flag: 'available' = dt_ata_in present, 'eta_data_unavailable' = missing
    eta_data_status VARCHAR(25) DEFAULT 'available',

    -- Business fields
    trip_status VARCHAR(20),
    is_active VARCHAR(5),
    trip_close_remark TEXT,
    material_desc VARCHAR(500),
    invoice_no VARCHAR(100),
    invoice_date VARCHAR(50),
    ref_no VARCHAR(100),
    ref_date VARCHAR(50),
    entry_type VARCHAR(50),
    own_market_type VARCHAR(50),
    running_sts VARCHAR(50),
    trip_seq INT,
    delay_by DECIMAL(10,2),

    -- Device info
    device_id VARCHAR(100),
    device_type VARCHAR(50),

    -- Metadata
    entity_id INT,
    cnr_id INT,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    track_link TEXT,
    data_string TEXT,

    -- Data quality flags
    is_5am_default TINYINT(1) DEFAULT 0,

    -- Extra columns for ML
    weather_conditions VARCHAR(100),
    fuel_consumed DECIMAL(10,2),
    load_weight_kg DECIMAL(10,2),

    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,
    FOREIGN KEY (origin_id) REFERENCES locations(id) ON DELETE SET NULL,
    FOREIGN KEY (destination_id) REFERENCES locations(id) ON DELETE SET NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- INDEXES FOR TRIPS (Performance Critical)
-- ============================================

CREATE INDEX idx_trips_driver_id ON trips(driver_id);
CREATE INDEX idx_trips_vehicle_id ON trips(vehicle_id);
CREATE INDEX idx_trips_origin_dest ON trips(origin_id, destination_id);
CREATE INDEX idx_trips_eta_met ON trips(eta_met);
CREATE INDEX idx_trips_trip_start ON trips(trip_start);
CREATE INDEX idx_trips_status ON trips(trip_status);
CREATE INDEX idx_trips_driver_start ON trips(driver_id, trip_start DESC);
CREATE INDEX idx_trips_eta_data_status ON trips(eta_data_status);

-- ============================================
-- WAYPOINTS TABLE (GPS tracking data from Excel)
-- ============================================

CREATE TABLE IF NOT EXISTS waypoints (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT,
    trip_id INT,
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    speed_kmph DECIMAL(8,2),
    status VARCHAR(100),
    location_text TEXT,
    distance_from_prev DECIMAL(10,2),
    recorded_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE SET NULL,

    INDEX idx_waypoints_vehicle_time (vehicle_id, recorded_at DESC),
    INDEX idx_waypoints_trip (trip_id),
    INDEX idx_waypoints_recorded (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- FILE UPLOADS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS file_uploads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    original_filename VARCHAR(500) NOT NULL,
    stored_filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_size_bytes BIGINT,
    upload_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    total_records INT,
    records_processed INT DEFAULT 0,
    records_failed INT DEFAULT 0,
    error_summary JSON,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_started_at DATETIME,
    processing_completed_at DATETIME,

    INDEX idx_uploads_status (status),
    INDEX idx_uploads_date (uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- ML MODEL REGISTRY
-- ============================================

CREATE TABLE IF NOT EXISTS ml_models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    version INT NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    target_variable VARCHAR(100) NOT NULL,
    metrics JSON,
    feature_columns JSON,
    hyperparameters JSON,
    model_artifact_path VARCHAR(500),
    training_data_count INT,
    training_data_start DATETIME,
    training_data_end DATETIME,
    is_active TINYINT(1) DEFAULT 0,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    UNIQUE KEY uq_model_version (model_name, version),
    INDEX idx_models_active (model_name, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- PREDICTIONS LOG (for ML monitoring)
-- ============================================

CREATE TABLE IF NOT EXISTS predictions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    trip_id INT,
    driver_id INT,
    input_features JSON NOT NULL,
    predicted_value DECIMAL(12,4),
    prediction_type VARCHAR(50) NOT NULL,
    confidence_score DECIMAL(5,4),
    actual_value DECIMAL(12,4),
    prediction_error DECIMAL(12,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (model_id) REFERENCES ml_models(id) ON DELETE CASCADE,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL,

    INDEX idx_predictions_model_date (model_id, created_at DESC),
    INDEX idx_predictions_trip (trip_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- ALERTS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(30) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    trip_id INT,
    driver_id INT,
    vehicle_id INT,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    metadata JSON,
    is_read TINYINT(1) DEFAULT 0,
    is_acknowledged TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at DATETIME,

    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,

    INDEX idx_alerts_unread (is_acknowledged, severity, created_at DESC),
    INDEX idx_alerts_driver (driver_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- VIEWS (MySQL doesn't have materialized views,
-- so we use regular views + summary tables)
-- ============================================

-- Summary table: refreshed by script after data load
CREATE TABLE IF NOT EXISTS driver_summary (
    driver_id INT PRIMARY KEY,
    driver_name VARCHAR(255),
    driver_mobile VARCHAR(20),
    total_trips INT DEFAULT 0,
    eta_met_count INT DEFAULT 0,
    eta_success_rate DECIMAL(6,2) DEFAULT 0,
    avg_duration_min DECIMAL(12,2),
    max_duration_min DECIMAL(12,2),
    min_duration_min DECIMAL(12,2),
    avg_speed_kmph DECIMAL(8,2),
    vehicles_used INT DEFAULT 0,
    total_distance_km DECIMAL(14,2),
    avg_distance_km DECIMAL(10,2),
    avg_eta_delay_min DECIMAL(12,2),
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS route_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    origin VARCHAR(255),
    destination VARCHAR(255),
    route_name VARCHAR(510),
    trip_count INT DEFAULT 0,
    avg_duration_min DECIMAL(12,2),
    avg_speed_kmph DECIMAL(8,2),
    eta_success_rate DECIMAL(6,2),
    avg_distance_km DECIMAL(10,2),
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_route (origin, destination),
    INDEX idx_route_count (trip_count DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS vehicle_summary (
    vehicle_id INT PRIMARY KEY,
    asset_id VARCHAR(50),
    asset_type VARCHAR(100),
    total_trips INT DEFAULT 0,
    drivers_used INT DEFAULT 0,
    avg_speed_kmph DECIMAL(8,2),
    total_distance_km DECIMAL(14,2),
    avg_distance_km DECIMAL(10,2),
    eta_success_rate DECIMAL(6,2),
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS daily_fleet_stats (
    stat_date DATE PRIMARY KEY,
    total_trips INT DEFAULT 0,
    total_distance_km DECIMAL(14,2),
    avg_speed DECIMAL(8,2),
    eta_success_rate DECIMAL(6,2),
    active_drivers INT DEFAULT 0,
    active_vehicles INT DEFAULT 0,
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS customer_summary (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(255),
    total_trips INT DEFAULT 0,
    total_distance_km DECIMAL(14,2),
    avg_distance_km DECIMAL(10,2),
    avg_duration_min DECIMAL(12,2),
    eta_success_rate DECIMAL(6,2),
    unique_routes INT DEFAULT 0,
    unique_drivers INT DEFAULT 0,
    unique_vehicles INT DEFAULT 0,
    first_trip_date DATE,
    last_trip_date DATE,
    avg_trips_per_week DECIMAL(10,2),
    top_origin VARCHAR(255),
    top_destination VARCHAR(255),
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS route_time_patterns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    origin VARCHAR(255),
    destination VARCHAR(255),
    hour_of_day TINYINT,
    day_of_week TINYINT,
    avg_duration DECIMAL(12,2),
    trip_count INT DEFAULT 0,
    eta_success_rate DECIMAL(6,2),
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_route_time (origin, destination, hour_of_day, day_of_week)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
