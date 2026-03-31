import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, TrendingUp, TrendingDown, Minus, Search } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import Spinner from '../components/ui/Spinner';
import Badge from '../components/ui/Badge';
import { useApi } from '../hooks/useApi';
import { getClients } from '../services/ml';

export default function ClientList() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<string>('total_trips');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const { data, loading } = useApi<any>(() => getClients(), []);

  const clients = (data?.data?.clients || data?.clients || []) as any[];
  const totalClients = data?.data?.total_clients || data?.total_clients || 0;
  const withForecast = data?.data?.clients_with_forecast || data?.clients_with_forecast || 0;

  const filtered = clients.filter((c: any) =>
    c.client.toLowerCase().includes(search.toLowerCase())
  );

  const sorted = [...filtered].sort((a, b) => {
    const aVal = a[sortBy] ?? 0;
    const bVal = b[sortBy] ?? 0;
    if (typeof aVal === 'string') return sortOrder === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
  });

  const handleSort = useCallback((col: string) => {
    if (sortBy === col) {
      setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortOrder('desc');
    }
  }, [sortBy]);

  const trendIcon = (trend: string) => {
    if (trend === 'growing') return <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />;
    if (trend === 'declining') return <TrendingDown className="w-3.5 h-3.5 text-red-400" />;
    return <Minus className="w-3.5 h-3.5 text-gray-500" />;
  };

  const trendVariant = (trend: string): 'success' | 'danger' | 'neutral' => {
    if (trend === 'growing') return 'success';
    if (trend === 'declining') return 'danger';
    return 'neutral';
  };

  const SortHeader = ({ col, label }: { col: string; label: string }) => (
    <th onClick={() => handleSort(col)}
      className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-gray-200 select-none">
      <span className="flex items-center gap-1">
        {label}
        {sortBy === col && <span className="text-blue-400">{sortOrder === 'asc' ? '↑' : '↓'}</span>}
      </span>
    </th>
  );

  return (
    <PageContainer title="Clients">
      {/* Summary bar */}
      <div className="flex items-center gap-6 mb-6">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-blue-400" />
          <span className="text-sm text-gray-400">Total Clients: <span className="text-white font-semibold">{totalClients.toLocaleString()}</span></span>
        </div>
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-emerald-400" />
          <span className="text-sm text-gray-400">With Forecasts: <span className="text-white font-semibold">{withForecast}</span></span>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-md">
        <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search clients..."
          className="w-full pl-10 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-blue-500"
        />
      </div>

      {loading ? <Spinner /> : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-800/50">
                <tr>
                  <SortHeader col="client" label="Client" />
                  <SortHeader col="total_trips" label="Total Trips" />
                  <SortHeader col="avg_trips_per_week" label="Avg/Week" />
                  <SortHeader col="active_weeks" label="Active Weeks" />
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Trend</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Forecast</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sorted.slice(0, 100).map((c: any) => (
                  <tr key={c.client}
                    onClick={() => navigate(`/clients/${encodeURIComponent(c.client)}`)}
                    className="hover:bg-gray-800/50 cursor-pointer transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-blue-400 shrink-0" />
                        <span className="text-sm font-medium text-white truncate max-w-[250px]">{c.client}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{c.total_trips?.toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-gray-300">{c.avg_trips_per_week?.toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-gray-300">{c.active_weeks}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {trendIcon(c.trend)}
                        <Badge label={c.trend || 'unknown'} variant={trendVariant(c.trend)} />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {c.has_forecast
                        ? <Badge label="Available" variant="success" />
                        : <Badge label="N/A" variant="neutral" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {sorted.length === 0 && (
            <div className="p-8 text-center text-gray-500 text-sm">
              {search ? `No clients matching "${search}"` : 'No client data available. Train the client_demand_forecaster model first.'}
            </div>
          )}
          {sorted.length > 100 && (
            <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-500">
              Showing 100 of {sorted.length} clients. Use search to narrow results.
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
