import { useNavigate } from 'react-router-dom';
import { MapPin, Users, Truck, Gauge, Target, TrendingUp } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import KPICard from '../components/ui/KPICard';
import AreaChart from '../components/charts/AreaChart';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import { useApi } from '../hooks/useApi';
import { getFleetSummary, getDailyTrend, getTopDrivers, getRecentAlerts } from '../services/dashboard';
import { CHART_COLORS } from '../lib/colors';
import { SEVERITY_STYLES } from '../lib/constants';
import { formatNumber, formatDistance, formatSpeed, formatPercent, formatDateTime } from '../lib/formatters';
import type { FleetSummary, DailyTrend, TopDriver, AlertOut } from '../types/dashboard';

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: summary, loading: sLoad } = useApi<FleetSummary>(() => getFleetSummary());
  const { data: trend } = useApi<DailyTrend[]>(() => getDailyTrend(30));
  const { data: drivers } = useApi<TopDriver[]>(() => getTopDrivers(10));
  const { data: alerts } = useApi<AlertOut[]>(() => getRecentAlerts(10));

  const etaColor = summary ? (summary.eta_success_rate != null && summary.eta_success_rate >= 90 ? 'green' : summary.eta_success_rate != null && summary.eta_success_rate >= 80 ? 'amber' : 'red') : 'red';

  return (
    <PageContainer title="Dashboard">
      {sLoad ? <Spinner /> : summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <KPICard label="Total Trips" value={formatNumber(summary.total_trips)} icon={MapPin} color="blue" />
          <KPICard label="Active Drivers" value={formatNumber(summary.total_drivers)} icon={Users} color="green" />
          <KPICard label="Vehicles" value={formatNumber(summary.total_vehicles)} icon={Truck} color="amber" />
          <KPICard label="Total Distance" value={formatDistance(summary.total_distance_km)} icon={Gauge} color="purple" />
          <KPICard label="Avg Speed" value={formatSpeed(summary.avg_speed_kmph)} icon={TrendingUp} color="cyan" />
          <KPICard label="ETA Success Rate" value={formatPercent(summary.eta_success_rate)} icon={Target} color={etaColor} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold text-white mb-4">Daily Trip Trend</h2>
          {trend ? (
            <AreaChart data={trend} xKey="stat_date" series={[{ key: 'total_trips', color: CHART_COLORS.primary, label: 'Trips' }]} height={280} />
          ) : <Spinner />}
        </div>
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold text-white mb-4">ETA Success Rate Trend</h2>
          {trend ? (
            <AreaChart data={trend} xKey="stat_date" series={[{ key: 'eta_success_rate', color: CHART_COLORS.secondary, label: 'ETA Rate %' }]} height={280} />
          ) : <Spinner />}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold text-white mb-4">Top Drivers</h2>
          {drivers ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="px-3 py-2 text-left text-xs text-gray-400">#</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-400">Driver</th>
                  <th className="px-3 py-2 text-right text-xs text-gray-400">Trips</th>
                  <th className="px-3 py-2 text-right text-xs text-gray-400">ETA Rate</th>
                  <th className="px-3 py-2 text-right text-xs text-gray-400">Speed</th>
                </tr>
              </thead>
              <tbody>
                {drivers.map((d, i) => (
                  <tr key={d.driver_id} onClick={() => navigate(`/drivers/${d.driver_id}`)}
                    className="border-b border-gray-800/50 hover:bg-gray-800/50 cursor-pointer transition-colors">
                    <td className="px-3 py-2 text-gray-500">{i + 1}</td>
                    <td className="px-3 py-2 text-gray-200">{d.driver_name}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{formatNumber(d.total_trips)}</td>
                    <td className="px-3 py-2 text-right">
                      <span className={d.eta_success_rate >= 90 ? 'text-emerald-400' : d.eta_success_rate >= 80 ? 'text-amber-400' : 'text-red-400'}>
                        {formatPercent(d.eta_success_rate)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">{formatSpeed(d.avg_speed_kmph)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Spinner />}
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Alerts</h2>
          {alerts ? (
            <div className="space-y-3">
              {alerts.length === 0 && <p className="text-gray-500 text-sm">No recent alerts</p>}
              {alerts.map(a => (
                <div key={a.id} className={`rounded-lg px-4 py-3 ${SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.info}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">{a.title}</span>
                    <Badge label={a.severity} variant={a.severity === 'critical' || a.severity === 'high' ? 'danger' : a.severity === 'warning' || a.severity === 'medium' ? 'warning' : 'info'} />
                  </div>
                  {a.message && <p className="text-xs opacity-80 line-clamp-2">{a.message}</p>}
                  {a.created_at && <p className="text-xs opacity-60 mt-1">{formatDateTime(a.created_at)}</p>}
                </div>
              ))}
            </div>
          ) : <Spinner />}
        </div>
      </div>
    </PageContainer>
  );
}
