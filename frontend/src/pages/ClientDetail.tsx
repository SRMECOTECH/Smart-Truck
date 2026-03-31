import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Building2, Calendar, TrendingUp, TrendingDown, Minus,
  MapPin, Truck, BarChart3,
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart as RechartsBar, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from 'recharts';
import PageContainer from '../components/layout/PageContainer';
import Spinner from '../components/ui/Spinner';
import Badge from '../components/ui/Badge';
import KPICard from '../components/ui/KPICard';
import { getClientProfile, getClientForecast } from '../services/ml';

const BAR_COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#2563eb', '#4f46e5', '#7c3aed'];
const DOW_COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#10b981', '#f59e0b', '#ef4444'];

export default function ClientDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const clientName = decodeURIComponent(name || '');

  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientName) return;
    setLoading(true);
    Promise.all([
      getClientProfile(clientName).then(r => r.data).catch(() => null),
      getClientForecast(clientName).then(r => r.data).catch(() => null),
    ]).then(([prof, fc]) => {
      if (prof?.error) setError(prof.error);
      else setProfile(prof);
      if (fc && !fc.error) setForecast(fc);
      setLoading(false);
    });
  }, [clientName]);

  if (loading) return <PageContainer title="Client"><Spinner /></PageContainer>;
  if (error) {
    return (
      <PageContainer title="Client">
        <button onClick={() => navigate('/clients')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to Clients
        </button>
        <div className="bg-red-950/30 border border-red-800/40 rounded-lg p-6 text-center">
          <p className="text-red-400">{error}</p>
        </div>
      </PageContainer>
    );
  }

  const prof = profile?.profile || {};
  const fc = forecast?.forecast || profile?.forecast || {};
  const resolvedName = profile?.client || clientName;

  const trendColor = fc.trend === 'growing' ? 'text-emerald-400' : fc.trend === 'declining' ? 'text-red-400' : 'text-amber-400';
  const trendVariant: 'success' | 'danger' | 'warning' = fc.trend === 'growing' ? 'success' : fc.trend === 'declining' ? 'danger' : 'warning';
  const TrendIcon = fc.trend === 'growing' ? TrendingUp : fc.trend === 'declining' ? TrendingDown : Minus;

  // Charts data
  const forecastChart = (fc.next_7_days || []).map((d: any) => ({
    day: d.day_of_week?.slice(0, 3), date: d.date, trips: d.predicted_trips,
  }));

  const dowData = prof.day_of_week_pattern
    ? Object.entries(prof.day_of_week_pattern).map(([day, count]) => ({ day, trips: count as number }))
    : [];

  const monthlyData = prof.monthly_trend
    ? Object.entries(prof.monthly_trend).map(([month, count]) => ({ month, trips: count as number }))
    : [];

  return (
    <PageContainer title={resolvedName}>
      {/* Back button */}
      <button onClick={() => navigate('/clients')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-6 text-sm">
        <ArrowLeft className="w-4 h-4" /> Back to Clients
      </button>

      {/* Header */}
      <div className="bg-gradient-to-r from-blue-900/40 to-indigo-900/30 rounded-xl border border-blue-800/30 p-6 mb-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl bg-blue-600/30 flex items-center justify-center">
            <Building2 className="w-7 h-7 text-blue-400" />
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">{resolvedName}</h1>
            <div className="flex items-center gap-4 mt-1 text-sm text-gray-400">
              {prof.first_trip && <span>Since {prof.first_trip}</span>}
              {prof.last_trip && <span>Last trip: {prof.last_trip}</span>}
            </div>
          </div>
          {fc.trend && (
            <div className="flex items-center gap-2">
              <TrendIcon className={`w-5 h-5 ${trendColor}`} />
              <Badge label={`${fc.trend} ${fc.growth_pct_30d != null ? (fc.growth_pct_30d > 0 ? '+' : '') + fc.growth_pct_30d + '%' : ''}`} variant={trendVariant} />
            </div>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KPICard label="Total Trips" value={prof.total_trips?.toLocaleString() || '0'} icon={Truck} color="blue" />
        <KPICard label="Avg Trips/Week" value={prof.avg_trips_per_week?.toLocaleString() || '0'} icon={BarChart3} color="purple" />
        <KPICard label="Active Weeks" value={prof.active_weeks || 0} icon={Calendar} color="cyan" />
        <KPICard
          label="Predicted Next Week"
          value={fc.total_predicted_week?.toFixed(0) || 'N/A'}
          icon={TrendingUp}
          color="green"
        />
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* 7-day forecast chart */}
        {forecastChart.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <p className="text-sm font-medium text-gray-300 mb-3">7-Day Demand Forecast</p>
            <ResponsiveContainer width="100%" height={220}>
              <RechartsBar data={forecastChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="day" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
                <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }} labelStyle={{ color: '#e5e7eb' }}
                  formatter={(val: any) => [`${Number(val).toFixed(0)} trips`, 'Predicted']} />
                <Bar dataKey="trips" radius={[6, 6, 0, 0]}>
                  {forecastChart.map((_: any, i: number) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                </Bar>
              </RechartsBar>
            </ResponsiveContainer>
          </div>
        )}

        {/* Day of week pattern */}
        {dowData.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <p className="text-sm font-medium text-gray-300 mb-3">Day of Week Pattern</p>
            <ResponsiveContainer width="100%" height={220}>
              <RechartsBar data={dowData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="day" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
                <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }} labelStyle={{ color: '#e5e7eb' }}
                  formatter={(val: any) => [`${Number(val).toLocaleString()} trips`, 'Total']} />
                <Bar dataKey="trips" radius={[6, 6, 0, 0]}>
                  {dowData.map((_: any, i: number) => <Cell key={i} fill={DOW_COLORS[i % DOW_COLORS.length]} />)}
                </Bar>
              </RechartsBar>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Monthly trend */}
      {monthlyData.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6">
          <p className="text-sm font-medium text-gray-300 mb-3">Monthly Trend</p>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={monthlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="month" tick={{ fill: '#9ca3af', fontSize: 10 }} angle={-45} textAnchor="end" height={60} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }} labelStyle={{ color: '#e5e7eb' }}
                formatter={(val: any) => [`${Number(val).toLocaleString()} trips`, 'Trips']} />
              <Area type="monotone" dataKey="trips" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top routes */}
      {prof.top_routes && prof.top_routes.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <p className="text-sm font-medium text-gray-300 mb-3">Top Routes</p>
          <div className="space-y-2">
            {prof.top_routes.map((r: any, i: number) => {
              const maxTrips = prof.top_routes[0]?.trips || 1;
              const pct = (r.trips / maxTrips) * 100;
              return (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-gray-500 w-5 text-right">{i + 1}</span>
                  <MapPin className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1 text-sm">
                      <span className="text-white truncate">{r.origin}</span>
                      <span className="text-gray-500">→</span>
                      <span className="text-white truncate">{r.destination}</span>
                    </div>
                    <div className="mt-1 bg-gray-800 rounded-full h-1.5 overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-gray-300 shrink-0">{r.trips.toLocaleString()}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Forecast details table */}
      {fc.next_7_days && fc.next_7_days.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 mt-6">
          <p className="text-sm font-medium text-gray-300 mb-3">Daily Forecast Details</p>
          <table className="w-full">
            <thead>
              <tr className="text-xs text-gray-500 uppercase">
                <th className="text-left py-2 px-3">Date</th>
                <th className="text-left py-2 px-3">Day</th>
                <th className="text-right py-2 px-3">Predicted Trips</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {fc.next_7_days.map((d: any) => (
                <tr key={d.date} className="text-sm">
                  <td className="py-2 px-3 text-gray-300">{d.date}</td>
                  <td className="py-2 px-3 text-gray-400">{d.day_of_week}</td>
                  <td className="py-2 px-3 text-right font-semibold text-blue-400">{d.predicted_trips?.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-700 text-sm font-semibold">
                <td colSpan={2} className="py-2 px-3 text-gray-300">Total</td>
                <td className="py-2 px-3 text-right text-blue-400">{fc.total_predicted_week?.toFixed(0)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </PageContainer>
  );
}
