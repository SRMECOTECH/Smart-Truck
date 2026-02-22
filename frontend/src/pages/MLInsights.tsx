import { useState } from 'react';
import { Play, Trash2 } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import ModelCard from '../components/ml/ModelCard';
import PredictionForm from '../components/ml/PredictionForm';
import Spinner from '../components/ui/Spinner';
import { useApi } from '../hooks/useApi';
import { listModels, predictEta, predictAnomaly, recommendDrivers, forecastTrips, trainAllModels, clearModelCache } from '../services/ml';
import type { MLModel } from '../types/ml';

const TABS = [
  { key: 'eta', label: 'ETA Prediction' },
  { key: 'anomaly', label: 'Anomaly Detection' },
  { key: 'recommend', label: 'Driver Recommender' },
  { key: 'forecast', label: 'Trip Forecast' },
] as const;

const ETA_FIELDS = [
  { name: 'origin', label: 'Origin', type: 'text' as const, required: true, placeholder: 'e.g. Mumbai' },
  { name: 'destination', label: 'Destination', type: 'text' as const, required: true, placeholder: 'e.g. Delhi' },
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

export default function MLInsights() {
  const { data: models, loading: modelsLoading, refetch } = useApi<MLModel[]>(() => listModels());
  const [activeTab, setActiveTab] = useState<TabKey>('eta');
  const [predLoading, setPredLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [trainLoading, setTrainLoading] = useState(false);
  const [cacheLoading, setCacheLoading] = useState(false);

  const handlePredict = async (values: Record<string, any>) => {
    setPredLoading(true);
    setResult(null);
    try {
      let res;
      if (activeTab === 'eta') {
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
      case 'forecast': return []; // No input fields - just a button
      default: return ETA_FIELDS;
    }
  };

  return (
    <PageContainer title="ML Insights">
      <div className="mb-8">
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
        {modelsLoading ? <Spinner /> : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(Array.isArray(models) ? models : (models as any)?.data || []).map((m: MLModel) => <ModelCard key={m.id} model={m} />)}
            {models?.length === 0 && <p className="text-gray-500 text-sm col-span-full">No models trained yet</p>}
          </div>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Predictions</h2>
        <div className="bg-gray-800 rounded-lg p-1 flex gap-1 mb-6 w-fit flex-wrap">
          {TABS.map(tab => (
            <button key={tab.key} onClick={() => { setActiveTab(tab.key); setResult(null); }}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.key ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}>
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'forecast' ? (
          <div>
            <button onClick={() => handlePredict({})} disabled={predLoading}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors mb-4">
              {predLoading ? 'Loading...' : 'Get Trip Forecast'}
            </button>
            {result && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mt-4">
                <pre className="text-sm text-gray-300 overflow-auto max-h-96 whitespace-pre-wrap">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <PredictionForm
            fields={getFields()}
            onSubmit={handlePredict}
            loading={predLoading}
            result={result}
          />
        )}
      </div>
    </PageContainer>
  );
}
