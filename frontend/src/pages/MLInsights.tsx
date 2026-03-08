import { useState } from 'react';
import { Play, Trash2, Clock, MapPin, Users, TrendingUp, TrendingDown, Star, Award, AlertTriangle, CheckCircle, Calendar, Truck } from 'lucide-react';
import { ResponsiveContainer, BarChart as RechartsBar, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts';
import PageContainer from '../components/layout/PageContainer';
import ModelCard from '../components/ml/ModelCard';
import PredictionForm from '../components/ml/PredictionForm';
import Spinner from '../components/ui/Spinner';
import { useApi } from '../hooks/useApi';
import { listModels, predictEta, predictAnomaly, recommendDrivers, forecastTrips, trainAllModels, clearModelCache } from '../services/ml';
import type { MLModel } from '../types/ml';

const TABS = [
  { key: 'eta', label: 'ETA Prediction', icon: Clock },
  { key: 'anomaly', label: 'Anomaly Detection', icon: AlertTriangle },
  { key: 'recommend', label: 'Driver Recommender', icon: Users },
  { key: 'forecast', label: 'Trip Forecast', icon: TrendingUp },
] as const;

function getDefaultTripStart(): string {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

const ETA_FIELDS = [
  { name: 'origin', label: 'Origin', type: 'text' as const, required: true, placeholder: 'e.g. Mumbai' },
  { name: 'destination', label: 'Destination', type: 'text' as const, required: true, placeholder: 'e.g. Delhi' },
  { name: 'trip_start', label: 'Trip Start Date & Time', type: 'datetime-local' as const, required: true, defaultValue: getDefaultTripStart() },
  { name: 'driver_id', label: 'Driver ID', type: 'number' as const },
  { name: 'vehicle_id', label: 'Vehicle ID', type: 'number' as const },
  { name: 'trip_km', label: 'Trip Distance (km)', type: 'number' as const },
];

const ANOMALY_FIELDS = [
  { name: 'trip_duration_minutes', label: 'Trip Duration (min)', type: 'number' as const, required: true },
  { name: 'eta_delay_minutes', label: 'ETA Delay (min)', type: 'number' as const, required: true },
  { name: 'duration_ratio', label: 'Duration Ratio', type: 'number' as const, required: true },
  { name: 'delay_ratio', label: 'Delay Ratio', type: 'number' as const, required: true },
  { name: 'hour_deviation', label: 'Hour Deviation', type: 'number' as const, required: true },
  { name: 'is_night_trip', label: 'Night Trip', type: 'number' as const, placeholder: '0 or 1' },
];

const RECOMMEND_FIELDS = [
  { name: 'origin', label: 'Origin', type: 'text' as const, required: true, placeholder: 'e.g. Mumbai' },
  { name: 'destination', label: 'Destination', type: 'text' as const, required: true, placeholder: 'e.g. Delhi' },
  { name: 'top_n', label: 'Top N Drivers', type: 'number' as const, placeholder: '10' },
];

type TabKey = typeof TABS[number]['key'];

// ──────────────────────────────────────────────
// ETA Result Renderer
// ──────────────────────────────────────────────
function ETAResult({ result, tripStart }: { result: any; tripStart?: string }) {
  if (result?.error) return <ErrorCard message={result.error} />;

  const predictedMinutes = result?.predicted_duration_minutes;
  if (predictedMinutes == null) return <ErrorCard message="No prediction returned" />;

  // Compute arrival date/time
  const startDate = tripStart ? new Date(tripStart) : new Date();
  const arrivalDate = new Date(startDate.getTime() + predictedMinutes * 60 * 1000);

  const days = Math.floor(predictedMinutes / 1440);
  const hours = Math.floor((predictedMinutes % 1440) / 60);
  const mins = Math.round(predictedMinutes % 60);

  const durationParts: string[] = [];
  if (days > 0) durationParts.push(`${days}d`);
  if (hours > 0) durationParts.push(`${hours}h`);
  if (mins > 0) durationParts.push(`${mins}m`);
  const durationStr = durationParts.join(' ') || '0m';

  const formatDate = (d: Date) => d.toLocaleDateString('en-IN', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });
  const formatTime = (d: Date) => d.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: true,
  });

  return (
    <div className="space-y-4">
      {/* Main arrival card */}
      <div className="bg-gradient-to-br from-blue-900/60 to-indigo-900/60 rounded-xl border border-blue-700/40 p-5">
        <div className="flex items-center gap-2 mb-3">
          <Calendar className="w-5 h-5 text-blue-400" />
          <span className="text-sm font-medium text-blue-300">Estimated Arrival</span>
        </div>
        <p className="text-2xl font-bold text-white mb-1">{formatDate(arrivalDate)}</p>
        <p className="text-3xl font-bold text-blue-400">{formatTime(arrivalDate)}</p>
      </div>

      {/* Duration & details */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
          <p className="text-xs text-gray-500 mb-1">Trip Duration</p>
          <p className="text-lg font-bold text-white">{durationStr}</p>
          <p className="text-xs text-gray-500">{predictedMinutes.toFixed(0)} minutes</p>
        </div>
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
          <p className="text-xs text-gray-500 mb-1">Departure</p>
          <p className="text-sm font-semibold text-white">{formatDate(startDate)}</p>
          <p className="text-sm text-gray-400">{formatTime(startDate)}</p>
        </div>
      </div>

      {/* Comparison with averages */}
      {(result.route_avg_duration != null || result.driver_avg_duration != null) && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
          <p className="text-xs text-gray-500 mb-2">Comparison</p>
          <div className="space-y-2">
            {result.route_avg_duration != null && (
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">Route Average</span>
                <span className="text-sm text-gray-300">{formatDuration(result.route_avg_duration)}</span>
              </div>
            )}
            {result.driver_avg_duration != null && (
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">Driver Average</span>
                <span className="text-sm text-gray-300">{formatDuration(result.driver_avg_duration)}</span>
              </div>
            )}
            <div className="flex justify-between items-center border-t border-gray-800 pt-2">
              <span className="text-xs text-gray-400">ML Predicted</span>
              <span className="text-sm font-semibold text-blue-400">{formatDuration(predictedMinutes)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatDuration(minutes: number): string {
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

// ──────────────────────────────────────────────
// Anomaly Result Renderer
// ──────────────────────────────────────────────
function AnomalyResult({ result }: { result: any }) {
  if (result?.error) return <ErrorCard message={result.error} />;

  const isAnomaly = result?.is_anomalous;
  const score = result?.anomaly_score;
  const confidence = result?.confidence;

  return (
    <div className="space-y-4">
      {/* Main verdict */}
      <div className={`rounded-xl border p-5 ${
        isAnomaly
          ? 'bg-gradient-to-br from-red-900/50 to-orange-900/40 border-red-700/40'
          : 'bg-gradient-to-br from-emerald-900/50 to-green-900/40 border-emerald-700/40'
      }`}>
        <div className="flex items-center gap-3 mb-2">
          {isAnomaly ? (
            <AlertTriangle className="w-8 h-8 text-red-400" />
          ) : (
            <CheckCircle className="w-8 h-8 text-emerald-400" />
          )}
          <div>
            <p className="text-xl font-bold text-white">
              {isAnomaly ? 'Anomaly Detected' : 'Normal Trip'}
            </p>
            <p className="text-sm text-gray-400">
              {isAnomaly ? 'This trip shows unusual patterns' : 'This trip looks normal'}
            </p>
          </div>
        </div>
      </div>

      {/* Score details */}
      <div className="grid grid-cols-2 gap-3">
        {score != null && (
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
            <p className="text-xs text-gray-500 mb-1">Anomaly Score</p>
            <p className={`text-lg font-bold ${score < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
              {score.toFixed(3)}
            </p>
            <p className="text-xs text-gray-500">Negative = anomalous</p>
          </div>
        )}
        {confidence != null && (
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
            <p className="text-xs text-gray-500 mb-1">Confidence</p>
            <p className="text-lg font-bold text-blue-400">{(confidence * 100).toFixed(1)}%</p>
          </div>
        )}
      </div>

      {/* Additional details */}
      {result && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
          <p className="text-xs text-gray-500 mb-2">Details</p>
          <div className="space-y-1.5">
            {Object.entries(result).filter(([k]) =>
              !['error', 'is_anomalous', 'anomaly_score', 'confidence'].includes(k)
            ).map(([k, v]) => (
              <div key={k} className="flex justify-between items-center text-sm">
                <span className="text-gray-400">{k.replace(/_/g, ' ')}</span>
                <span className="text-gray-300">{typeof v === 'number' ? (v as number).toFixed(3) : String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────
// Driver Recommender Result Renderer
// ──────────────────────────────────────────────
function RecommenderResult({ result }: { result: any }) {
  if (result?.error) return <ErrorCard message={result.error} />;

  const drivers = result?.recommended_drivers || [];
  if (drivers.length === 0) return <ErrorCard message="No drivers found for this route" />;

  const getRankIcon = (idx: number) => {
    if (idx === 0) return <Award className="w-5 h-5 text-yellow-400" />;
    if (idx === 1) return <Award className="w-5 h-5 text-gray-300" />;
    if (idx === 2) return <Award className="w-5 h-5 text-amber-600" />;
    return <span className="w-5 h-5 flex items-center justify-center text-xs font-bold text-gray-500">#{idx + 1}</span>;
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-emerald-400';
    if (score >= 50) return 'text-amber-400';
    return 'text-red-400';
  };

  const getScoreBg = (score: number) => {
    if (score >= 70) return 'bg-emerald-950/50 border-emerald-800/40';
    if (score >= 50) return 'bg-amber-950/50 border-amber-800/40';
    return 'bg-red-950/50 border-red-800/40';
  };

  return (
    <div className="space-y-4">
      {/* Route summary */}
      <div className="flex items-center gap-3 bg-gray-900 rounded-lg border border-gray-800 p-3">
        <MapPin className="w-4 h-4 text-blue-400 shrink-0" />
        <div className="text-sm">
          <span className="text-white font-medium">{result.origin}</span>
          <span className="text-gray-500 mx-2">→</span>
          <span className="text-white font-medium">{result.destination}</span>
        </div>
        <div className="ml-auto flex gap-4 text-xs text-gray-500">
          <span>{result.total_candidates} candidates</span>
          <span>{result.drivers_with_route_exp} with route exp</span>
        </div>
      </div>

      {/* Driver cards */}
      <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
        {drivers.map((d: any, idx: number) => (
          <div key={d.driver_id} className={`rounded-lg border p-3 transition-colors hover:border-gray-600 ${
            idx === 0 ? 'bg-gradient-to-r from-yellow-950/30 to-gray-900 border-yellow-800/30' : 'bg-gray-900 border-gray-800'
          }`}>
            <div className="flex items-center gap-3">
              {/* Rank */}
              <div className="shrink-0">{getRankIcon(idx)}</div>

              {/* Name & ID */}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-white truncate">{d.driver_name || `Driver #${d.driver_id}`}</p>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span>ID: {d.driver_id}</span>
                  {d.has_route_experience && (
                    <span className="flex items-center gap-0.5 text-blue-400">
                      <Star className="w-3 h-3" /> {d.route_trips} route trips
                    </span>
                  )}
                  <span>{d.total_trips} total trips</span>
                </div>
              </div>

              {/* Composite score */}
              <div className={`shrink-0 px-3 py-1.5 rounded-lg border text-center ${getScoreBg(d.composite_score)}`}>
                <p className={`text-lg font-bold ${getScoreColor(d.composite_score)}`}>{d.composite_score.toFixed(1)}</p>
                <p className="text-[10px] text-gray-500 uppercase">Score</p>
              </div>
            </div>

            {/* Score breakdown bar */}
            <div className="mt-2 flex gap-1 h-1.5 rounded-full overflow-hidden">
              <div className="bg-purple-500 rounded-full" style={{ width: `${d.route_experience_score}%` }} title={`Route Exp: ${d.route_experience_score}`} />
              <div className="bg-emerald-500 rounded-full" style={{ width: `${d.eta_compliance_score}%` }} title={`ETA: ${d.eta_compliance_score}`} />
              <div className="bg-blue-500 rounded-full" style={{ width: `${d.speed_efficiency_score}%` }} title={`Speed: ${d.speed_efficiency_score}`} />
              <div className="bg-amber-500 rounded-full" style={{ width: `${d.consistency_score}%` }} title={`Consistency: ${d.consistency_score}`} />
            </div>
            <div className="mt-1 flex gap-3 text-[10px] text-gray-500">
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-purple-500 inline-block" />Route {d.route_experience_score}</span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />ETA {d.eta_compliance_score}</span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />Speed {d.speed_efficiency_score}</span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />Consistency {d.consistency_score}</span>
            </div>

            {/* Quick stats */}
            <div className="mt-2 flex gap-4 text-xs">
              <span className="text-gray-400">Speed: <span className="text-gray-300">{d.avg_speed_kmph} km/h</span></span>
              <span className="text-gray-400">ETA Rate: <span className={d.eta_success_rate >= 80 ? 'text-emerald-400' : d.eta_success_rate >= 60 ? 'text-amber-400' : 'text-red-400'}>{d.eta_success_rate}%</span></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
// Trip Forecast Result Renderer
// ──────────────────────────────────────────────
function ForecastResult({ result }: { result: any }) {
  if (result?.error) return <ErrorCard message={result.error} />;

  const fleet = result?.fleet_forecast;
  const topRoutes = result?.top_routes || {};
  const routeKeys = Object.keys(topRoutes);

  const fleetChartData = (fleet?.next_7_days || []).map((d: any) => ({
    day: d.day_of_week?.slice(0, 3),
    date: d.date,
    trips: d.predicted_trips,
  }));

  const trendIcon = fleet?.recent_trend === 'up'
    ? <TrendingUp className="w-4 h-4 text-emerald-400" />
    : <TrendingDown className="w-4 h-4 text-red-400" />;

  const BAR_COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#2563eb', '#4f46e5', '#7c3aed'];

  return (
    <div className="space-y-5">
      {/* Fleet summary cards */}
      {fleet && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Total Next Week" value={fleet.total_predicted_week?.toFixed(0)} icon={<Truck className="w-4 h-4 text-blue-400" />} />
            <StatCard label="Avg Daily (Historic)" value={fleet.historical_avg_daily?.toFixed(0)} icon={<TrendingUp className="w-4 h-4 text-purple-400" />} />
            <StatCard label="Recent 7d Avg" value={fleet.recent_avg_daily_7d?.toFixed(0)} icon={<Calendar className="w-4 h-4 text-indigo-400" />} />
            <div className="bg-gray-900 rounded-lg border border-gray-800 p-3 flex items-center gap-2">
              {trendIcon}
              <div>
                <p className="text-xs text-gray-500">Trend</p>
                <p className={`text-sm font-semibold capitalize ${fleet.recent_trend === 'up' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {fleet.recent_trend}
                </p>
              </div>
            </div>
          </div>

          {/* Fleet chart */}
          {fleetChartData.length > 0 && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <p className="text-sm font-medium text-gray-300 mb-3">Fleet-wide Daily Forecast (Next 7 Days)</p>
              <ResponsiveContainer width="100%" height={220}>
                <RechartsBar data={fleetChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="day" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                    labelStyle={{ color: '#e5e7eb' }}
                    formatter={(val: any) => [`${Number(val).toFixed(0)} trips`, 'Predicted']}
                  />
                  <Bar dataKey="trips" radius={[6, 6, 0, 0]}>
                    {fleetChartData.map((_: any, i: number) => (
                      <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </RechartsBar>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {/* Top routes */}
      {routeKeys.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <p className="text-sm font-medium text-gray-300 mb-3">Top Route Forecasts</p>
          <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
            {routeKeys.map(route => {
              const r = topRoutes[route];
              const trendColor = r.recent_trend === 'up' ? 'text-emerald-400' : r.recent_trend === 'down' ? 'text-red-400' : 'text-gray-400';
              return (
                <div key={route} className="flex items-center gap-3 bg-gray-800/50 rounded-lg border border-gray-700/50 px-3 py-2">
                  <MapPin className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white truncate">{route}</p>
                    <p className="text-xs text-gray-500">Avg {r.historical_avg_daily}/day</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-bold text-blue-400">{r.total_predicted_week?.toFixed(0)}</p>
                    <p className="text-[10px] text-gray-500">next week</p>
                  </div>
                  <span className={`text-xs font-medium capitalize ${trendColor}`}>{r.recent_trend}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {result?.generated_at && (
        <p className="text-xs text-gray-600 text-right">Generated: {new Date(result.generated_at).toLocaleString()}</p>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────
// Shared components
// ──────────────────────────────────────────────
function ErrorCard({ message }: { message: string }) {
  return (
    <div className="bg-red-950/30 border border-red-800/40 rounded-lg p-4 flex items-center gap-3">
      <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
      <p className="text-sm text-red-300">{message}</p>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon: React.ReactNode }) {
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <p className="text-xs text-gray-500">{label}</p>
      </div>
      <p className="text-lg font-bold text-white">{value}</p>
    </div>
  );
}

// ──────────────────────────────────────────────
// Main MLInsights Page
// ──────────────────────────────────────────────
export default function MLInsights() {
  const { data: models, loading: modelsLoading, refetch } = useApi<MLModel[]>(() => listModels());
  const [activeTab, setActiveTab] = useState<TabKey>('eta');
  const [predLoading, setPredLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [lastTripStart, setLastTripStart] = useState<string>('');
  const [trainLoading, setTrainLoading] = useState(false);
  const [cacheLoading, setCacheLoading] = useState(false);

  const handlePredict = async (values: Record<string, any>) => {
    setPredLoading(true);
    setResult(null);
    try {
      let res;
      if (activeTab === 'eta') {
        setLastTripStart(values.trip_start || '');
        res = await predictEta(values);
      } else if (activeTab === 'anomaly') {
        res = await predictAnomaly(values);
      } else if (activeTab === 'recommend') {
        res = await recommendDrivers({ origin: values.origin, destination: values.destination, top_n: Number(values.top_n) || 10 });
      } else {
        res = await forecastTrips();
      }
      setResult(res.data);
    } catch (err: any) {
      setResult({ error: err?.response?.data?.detail || err.message || 'Prediction failed' });
    } finally {
      setPredLoading(false);
    }
  };

  const handleTrainAll = async () => {
    setTrainLoading(true);
    try {
      await trainAllModels();
      refetch();
    } catch { /* ignore */ }
    setTrainLoading(false);
  };

  const handleClearCache = async () => {
    setCacheLoading(true);
    try { await clearModelCache(); } catch { /* ignore */ }
    setCacheLoading(false);
  };

  const getFields = () => {
    switch (activeTab) {
      case 'eta': return ETA_FIELDS;
      case 'anomaly': return ANOMALY_FIELDS;
      case 'recommend': return RECOMMEND_FIELDS;
      case 'forecast': return [];
      default: return ETA_FIELDS;
    }
  };

  const getResultRenderer = () => {
    switch (activeTab) {
      case 'eta': return (r: any) => <ETAResult result={r} tripStart={lastTripStart} />;
      case 'anomaly': return (r: any) => <AnomalyResult result={r} />;
      case 'recommend': return (r: any) => <RecommenderResult result={r} />;
      default: return undefined;
    }
  };

  const modelsList = Array.isArray(models) ? models : (models as any)?.data || [];

  return (
    <PageContainer title="ML Insights">
      {/* Trained Models Section */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Trained Models</h2>
          <div className="flex gap-2">
            <button onClick={handleTrainAll} disabled={trainLoading}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors">
              {trainLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Play className="w-4 h-4" />}
              Train All
            </button>
            <button onClick={handleClearCache} disabled={cacheLoading}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors">
              <Trash2 className="w-4 h-4" />
              Clear Cache
            </button>
          </div>
        </div>
        {modelsLoading ? <Spinner /> : modelsList.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {modelsList.map((m: MLModel) => <ModelCard key={m.id} model={m} />)}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No models trained yet. Click "Train All" to get started.</p>
        )}
      </div>

      {/* Predictions Section */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Predictions</h2>
        <div className="bg-gray-800 rounded-lg p-1 flex gap-1 mb-6 w-fit flex-wrap">
          {TABS.map(tab => {
            const Icon = tab.icon;
            return (
              <button key={tab.key} onClick={() => { setActiveTab(tab.key); setResult(null); }}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.key ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}>
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {activeTab === 'forecast' ? (
          <div>
            <button onClick={() => handlePredict({})} disabled={predLoading}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors mb-4">
              {predLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <TrendingUp className="w-4 h-4" />}
              {predLoading ? 'Loading...' : 'Get Trip Forecast'}
            </button>
            {predLoading && !result && <Spinner />}
            {result && <ForecastResult result={result} />}
          </div>
        ) : (
          <PredictionForm
            fields={getFields()}
            onSubmit={handlePredict}
            loading={predLoading}
            result={result}
            renderResult={getResultRenderer()}
            submitLabel={activeTab === 'recommend' ? 'Find Drivers' : activeTab === 'anomaly' ? 'Check Anomaly' : 'Predict ETA'}
          />
        )}
      </div>
    </PageContainer>
  );
}
