import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, MapPin, Clock, Gauge, Target } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import KPICard from '../components/ui/KPICard';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import { useApi } from '../hooks/useApi';
import { getTripDetail } from '../services/trips';
import { formatDuration, formatDistance, formatSpeed, formatDateTime } from '../lib/formatters';
import type { TripDetail as TripDetailType } from '../types/trip';

export default function TripDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const tripId = Number(id);
  const { data, loading } = useApi<TripDetailType>(() => getTripDetail(tripId), [tripId]);

  if (loading) return <Spinner />;
  if (!data) return <p className="text-gray-500">Trip not found</p>;

  const t = data.trip;

  return (
    <PageContainer title="">
      <button onClick={() => navigate('/trips')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-4 text-sm">
        <ArrowLeft className="w-4 h-4" /> Back to Trips
      </button>
      <h1 className="text-2xl font-bold text-white mb-6">Trip: {t.dispatch_entry_no}</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KPICard label="Duration" value={formatDuration(t.trip_duration_minutes)} icon={Clock} color="purple" />
        <KPICard label="Distance" value={formatDistance(t.trip_km)} icon={MapPin} color="blue" />
        <KPICard label="Avg Speed" value={formatSpeed(t.avg_speed_kmph)} icon={Gauge} color="cyan" />
        <KPICard label="ETA Met" value={t.eta_met ? 'Yes' : 'No'} icon={Target} color={t.eta_met ? 'green' : 'red'} />
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Trip Information</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-500">Driver</span>
              <Link to={`/drivers/${t.driver_id}`} className="text-blue-400 hover:underline">{t.driver_name}</Link>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Vehicle</span>
              <Link to={`/vehicles/${t.vehicle_id}`} className="text-blue-400 hover:underline">{t.asset_id}</Link>
            </div>
            <div className="flex justify-between"><span className="text-gray-500">Origin</span><span className="text-gray-300">{t.origin_name}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Destination</span><span className="text-gray-300">{t.destination_name}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Customer</span><span className="text-gray-300">{t.customer_name || '-'}</span></div>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-gray-500">Status</span><Badge label={t.trip_status} variant={t.trip_status === 'Completed' ? 'success' : 'info'} /></div>
            <div className="flex justify-between"><span className="text-gray-500">Start</span><span className="text-gray-300">{formatDateTime(t.trip_start)}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">End</span><span className="text-gray-300">{formatDateTime(t.trip_end)}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">ETA</span><span className="text-gray-300">{formatDateTime(t.trip_eta)}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Close Remark</span><span className="text-gray-300">{t.trip_close_remark || '-'}</span></div>
          </div>
        </div>
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-lg font-semibold text-white mb-4">Waypoints ({data.waypoints.length})</h2>
        {data.waypoints.length === 0 ? (
          <p className="text-gray-500 text-sm">No waypoints recorded</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="px-3 py-2 text-left text-xs text-gray-400">Time</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-400">Location</th>
                  <th className="px-3 py-2 text-right text-xs text-gray-400">Speed</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-400">Status</th>
                  <th className="px-3 py-2 text-right text-xs text-gray-400">Dist from Prev</th>
                </tr>
              </thead>
              <tbody>
                {data.waypoints.map((w, i) => (
                  <tr key={i} className="border-b border-gray-800/50">
                    <td className="px-3 py-2 text-gray-400">{formatDateTime(w.recorded_at)}</td>
                    <td className="px-3 py-2 text-gray-300">{w.location_text || '-'}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{formatSpeed(w.speed_kmph)}</td>
                    <td className="px-3 py-2 text-gray-300">{w.status || '-'}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{formatDistance(w.distance_from_prev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageContainer>
  );
}
