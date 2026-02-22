export interface MLModel {
  id: number;
  model_name: string;
  version: number;
  model_type: string;
  target_variable: string;
  metrics: Record<string, number>;
  feature_columns?: string[];
  training_data_count: number;
  is_active: number;
  trained_at: string | null;
}

export interface ETAPredictRequest {
  origin: string;
  destination: string;
  driver_id?: number;
  vehicle_id?: number;
  trip_km?: number;
  trip_start?: string;
}

export interface AnomalyCheckRequest {
  trip_duration_minutes: number;
  eta_delay_minutes: number;
  duration_ratio: number;
  delay_ratio: number;
  hour_deviation: number;
  is_night_trip: number;
}

export interface FuelPredictRequest {
  trip_km: number;
  trip_duration_minutes?: number;
  avg_speed_kmph?: number;
  hour?: number;
  day_of_week?: number;
  is_weekend?: number;
  month?: number;
  load_weight_kg?: number;
}

export interface RouteOptimizeRequest {
  origin: string;
  destination: string;
  trip_km?: number;
  hour?: number;
  day_of_week?: number;
}
