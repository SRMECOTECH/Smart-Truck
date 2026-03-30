import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Users, Truck, Gauge, Target, TrendingUp, Clock, ShieldCheck, AlertTriangle, Brain, Route, Building2, Sparkles, ArrowRight, Search } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import KPICard from '../components/ui/KPICard';
import AreaChart from '../components/charts/AreaChart';
import Spinner from '../components/ui/Spinner';
import { useApi } from '../hooks/useApi';
import { getFleetSummary, getDailyTrend, getTopDrivers } from '../services/dashboard';
import { predictEta, recommendDrivers } from '../services/ml';
import { CHART_COLORS } from '../lib/colors';
import { formatNumber, formatDistance, formatSpeed, formatPercent } from '../lib/formatters';
import type { FleetSummary, DailyTrend, TopDriver } from '../types/dashboard';

const ML_SHORTCUTS = [
  { label: 'ETA Predictor', desc: 'Predict trip duration', path: '/ml/eta', icon: Clock, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  { label: 'SLA Risk', desc: 'Check delivery risk', path: '/ml/sla', icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  { label: 'Anomaly Scan', desc: 'Detect trip anomalies', path: '/ml/anomaly', icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
  { label: 'Fatigue Monitor', desc: 'Driver safety check', path: '/ml/fatigue', icon: Brain, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  { label: 'Recommender', desc: 'Best driver for route', path: '/ml/recommender', icon: Users, color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
  { label: 'Demand Forecast', desc: '7-day trip forecast', path: '/ml/demand', icon: TrendingUp, color: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/20' },
];

function fmtDuration(minutes: number): string {
  if (minutes == null) return '-';
  const d = Math.floor(minutes / 1440);
  const h = Math.floor((minutes % 1440) / 60);
  const m = Math.round(minutes % 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  if (m > 0 || parts.length === 0) parts.push(`${m}m`);
  return parts.join(' ');
}

function QuickQuery() {
  const [mode, setMode] = useState<'eta' | 'recommend'>('eta');
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const canQuery = origin.trim() && destination.trim();

  const handleQuery = async () => {
    if (!canQuery) return;
    setLoading(true); setResult(null); setError('');
    try {
      if (mode === 'eta') {
        const res = await predictEta({ origin: origin.trim(), destination: destination.trim(), trip_start: new Date().toISOString() });
        setResult({ type: 'eta', data: res.data });
      } else {
        const res = await recommendDrivers({ origin: origin.trim(), destination: destination.trim(), top_n: 3 });
        setResult({ type: 'recommend', data: res.data });
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Query failed');
    }
    setLoading(false);
  };

  return (
    <div>
      {/* Mode Tabs */}
      <div className="flex gap-1 mb-3">
        <button onClick={() => { setMode('eta'); setResult(null); }}
          className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${mode === 'eta' ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' : 'text-gray-500 hover:text-gray-300'}`}>
          <Clock className="w-3 h-3 inline mr-1" />ETA
        </button>
        <button onClick={() => { setMode('recommend'); setResult(null); }}
          className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${mode === 'recommend' ? 'bg-cyan-600/20 text-cyan-400 border border-cyan-500/30' : 'text-gray-500 hover:text-gray-300'}`}>
          <Users className="w-3 h-3 inline mr-1" />Recommend
        </button>
      </div>

      {/* Inputs */}
      <div className="space-y-2 mb-3">
        <input type="text" value={origin} onChange={e => setOrigin(e.target.value)} placeholder="Origin (e.g. JHARSUGUDA)"
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500/50 transition-all" />
        <input type="text" value={destination} onChange={e => setDestination(e.target.value)} placeholder="Destination (e.g. CHENNAI)"
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500/50 transition-all" />
      </div>

      <button onClick={handleQuery} disabled={!canQuery || loading}
        className={`w-full py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
          canQuery ? 'bg-blue-600 hover:bg-blue-500 text-white' : 'bg-gray-800 text-gray-500 cursor-not-allowed'
        }`}>
        {loading ? <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          : <Sparkles className="w-3.5 h-3.5" />}
        {mode === 'eta' ? 'Predict ETA' : 'Find Drivers'}
      </button>

      {/* Result */}
      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}

      {result?.type === 'eta' && result.data?.predicted_duration_minutes != null && (
        <div className="mt-3 bg-blue-900/20 rounded-lg border border-blue-800/30 p-3 animate-scale-in">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-400">Predicted Duration</span>
            <span className="text-lg font-bold text-blue-400">{fmtDuration(result.data.predicted_duration_minutes)}</span>
          </div>
          {result.data.route_avg_duration != null && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Route Average</span>
              <span className="text-gray-400">{fmtDuration(result.data.route_avg_duration)}</span>
            </div>
          )}
          <button onClick={() => navigate('/ml/eta')} className="text-[11px] text-blue-400 hover:text-blue-300 mt-2 flex items-center gap-1">
            Full prediction <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      )}

      {result?.type === 'recommend' && (
        <div className="mt-3 space-y-1.5 animate-scale-in">
          {(result.data?.experienced_on_route || []).slice(0, 3).map((d: any, i: number) => (
            <div key={d.driver_id} onClick={() => navigate(`/drivers/${d.driver_id}`)}
              className="flex items-center justify-between bg-cyan-900/15 rounded-lg border border-cyan-800/25 px-3 py-2 cursor-pointer hover:bg-cyan-900/25 transition-colors">
              <div>
                <p className="text-sm text-white">{d.driver_name}</p>
                <p className="text-[11px] text-gray-500">{d.route_trips} trips on route | ETA: {d.eta_success_rate?.toFixed(0)}%</p>
              </div>
              <span className="text-sm font-bold text-cyan-400">{d.composite_score?.toFixed(0)}</span>
            </div>
          ))}
          {(result.data?.experienced_on_route || []).length === 0 && (
            <p className="text-xs text-gray-500 text-center py-2">No experienced drivers for this route</p>
          )}
          <button onClick={() => navigate('/ml/recommender')} className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
            Full recommendations <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: summary, loading: sLoad } = useApi<FleetSummary>(() => getFleetSummary());
  const { data: trend } = useApi<DailyTrend[]>(() => getDailyTrend(30));
  const { data: drivers } = useApi<TopDriver[]>(() => getTopDrivers(10));

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

        {/* ML Quick Actions + Query */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-blue-400" /> ML Quick Actions
            </h2>
            <button onClick={() => navigate('/ml')} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              All Models <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {/* Shortcut Grid */}
          <div className="grid grid-cols-3 gap-2 mb-5">
            {ML_SHORTCUTS.map(s => (
              <button key={s.path} onClick={() => navigate(s.path)}
                className={`${s.bg} border ${s.border} rounded-lg p-2.5 text-left hover:scale-[1.03] transition-all`}>
                <s.icon className={`w-4 h-4 ${s.color} mb-1`} />
                <p className="text-xs font-medium text-white">{s.label}</p>
                <p className="text-[10px] text-gray-500">{s.desc}</p>
              </button>
            ))}
          </div>

          {/* Inline Quick Query */}
          <div className="border-t border-gray-800 pt-4">
            <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
              <Search className="w-4 h-4 text-gray-500" /> Quick Query
            </h3>
            <QuickQuery />
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
