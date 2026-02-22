import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Truck, Users, Gauge, Target } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import KPICard from '../components/ui/KPICard';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import { useApi } from '../hooks/useApi';
import { getVehicleDetail } from '../services/vehicles';
import { formatNumber, formatPercent, formatSpeed, formatDistance, formatDuration, formatDateTime } from '../lib/formatters';
import type { VehicleDetail as VehicleDetailType } from '../types/vehicle';

export default function VehicleDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const vehicleId = Number(id);
  const { data, loading } = useApi<VehicleDetailType>(() => getVehicleDetail(vehicleId), [vehicleId]);

  if (loading) return <Spinner />;
  if (!data) return <p className="text-gray-500">Vehicle not found</p>;

  const s = data.summary;

  return (
    <PageContainer title="">
      <button onClick={() => navigate('/vehicles')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-4 text-sm">
        <ArrowLeft className="w-4 h-4" /> Back to Vehicles
      </button>
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-white">{s.asset_id}</h1>
        <Badge label={s.asset_type} variant="info" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KPICard label="Total Trips" value={formatNumber(s.total_trips)} icon={Truck} color="blue" />
        <KPICard label="Drivers Used" value={formatNumber(s.drivers_used)} icon={Users} color="green" />
        <KPICard label="Avg Speed" value={formatSpeed(s.avg_speed_kmph)} icon={Gauge} color="cyan" />
        <KPICard label="ETA Rate" value={formatPercent(s.eta_success_rate)} icon={Target} color={s.eta_success_rate >= 90 ? 'green' : s.eta_success_rate >= 80 ? 'amber' : 'red'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold text-white mb-4">Drivers</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="px-3 py-2 text-left text-xs text-gray-400">#</th>
                <th className="px-3 py-2 text-left text-xs text-gray-400">Driver</th>
                <th className="px-3 py-2 text-right text-xs text-gray-400">Trips</th>
              </tr>
            </thead>
            <tbody>
              {data.drivers_used.map((d, i) => (
                <tr key={d.driver_id} onClick={() => navigate(`/drivers/${d.driver_id}`)}
                  className="border-b border-gray-800/50 hover:bg-gray-800/50 cursor-pointer transition-colors">
                  <td className="px-3 py-2 text-gray-500">{i + 1}</td>
                  <td className="px-3 py-2 text-gray-200">{d.driver_name}</td>
                  <td className="px-3 py-2 text-right text-gray-300">{formatNumber(d.trip_count)}</td>
                </tr>
              ))}
              {data.drivers_used.length === 0 && (
                <tr><td colSpan={3} className="px-3 py-6 text-center text-gray-500">No driver data</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold text-white mb-4">Distance Summary</h2>
          <div className="space-y-4 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Total Distance</span><span className="text-gray-200 font-semibold">{formatDistance(s.total_distance_km)}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Avg per Trip</span><span className="text-gray-200 font-semibold">{formatDistance(s.avg_distance_km)}</span></div>
          </div>
        </div>
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Trips</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="px-3 py-2 text-left text-xs text-gray-400">Dispatch#</th>
                <th className="px-3 py-2 text-left text-xs text-gray-400">Driver</th>
                <th className="px-3 py-2 text-left text-xs text-gray-400">Origin</th>
                <th className="px-3 py-2 text-left text-xs text-gray-400">Destination</th>
                <th className="px-3 py-2 text-left text-xs text-gray-400">Start</th>
                <th className="px-3 py-2 text-right text-xs text-gray-400">Duration</th>
                <th className="px-3 py-2 text-center text-xs text-gray-400">ETA Met</th>
                <th className="px-3 py-2 text-right text-xs text-gray-400">Speed</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_trips.map(t => (
                <tr key={t.id} onClick={() => navigate(`/trips/${t.id}`)}
                  className="border-b border-gray-800/50 hover:bg-gray-800/50 cursor-pointer transition-colors">
                  <td className="px-3 py-2 text-gray-300">{t.dispatch_entry_no}</td>
                  <td className="px-3 py-2 text-gray-300">{t.driver_name}</td>
                  <td className="px-3 py-2 text-gray-300">{t.origin_name}</td>
                  <td className="px-3 py-2 text-gray-300">{t.destination_name}</td>
                  <td className="px-3 py-2 text-gray-400">{formatDateTime(t.trip_start)}</td>
                  <td className="px-3 py-2 text-right text-gray-300">{formatDuration(t.trip_duration_minutes)}</td>
                  <td className="px-3 py-2 text-center"><Badge label={t.eta_met ? 'Yes' : 'No'} variant={t.eta_met ? 'success' : 'danger'} /></td>
                  <td className="px-3 py-2 text-right text-gray-300">{formatSpeed(t.avg_speed_kmph)}</td>
                </tr>
              ))}
              {data.recent_trips.length === 0 && (
                <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-500">No recent trips</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </PageContainer>
  );
}
