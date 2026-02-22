export interface VehicleSummaryRow {
  vehicle_id: number;
  asset_id: string;
  asset_type: string;
  total_trips: number;
  drivers_used: number;
  avg_speed_kmph: number;
  total_distance_km: number;
  avg_distance_km: number;
  eta_success_rate: number;
}

export interface VehicleDriver {
  driver_id: number;
  driver_name: string;
  trip_count: number;
}

export interface VehicleDetail {
  summary: VehicleSummaryRow;
  drivers_used: VehicleDriver[];
  recent_trips: Array<{
    id: number;
    dispatch_entry_no: string;
    driver_name: string;
    origin_name: string;
    destination_name: string;
    trip_start: string;
    trip_duration_minutes: number;
    eta_met: boolean;
    avg_speed_kmph: number;
  }>;
}
