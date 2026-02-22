import { mlApi } from './api';

export const predictEta = (data: any) => mlApi.post('/ml/predict/eta', data);
export const predictAnomaly = (data: any) => mlApi.post('/ml/predict/anomaly', data);
export const getDriverScores = (limit = 100) => mlApi.get(`/ml/drivers/scores?limit=${limit}`);
export const getDriverScore = (id: number) => mlApi.get(`/ml/drivers/${id}/score`);
export const getDemandForecast = (route?: string) => mlApi.get('/ml/forecast/demand', { params: route ? { route } : {} });
export const optimizeRoute = (data: any) => mlApi.post('/ml/optimize/route', data);
export const getHubLocations = () => mlApi.get('/ml/optimize/hubs');
export const recommendDrivers = (data: { origin: string; destination: string; top_n?: number }) => mlApi.post('/ml/recommend/drivers', data);
export const forecastTrips = (route?: string) => mlApi.get('/ml/forecast/trips', { params: route ? { route } : {} });
export const listModels = () => mlApi.get('/ml/models');
export const getModelComparison = () => mlApi.get('/ml/models/comparison');
export const trainModel = (name: string) => mlApi.post(`/ml/train/${name}`);
export const trainAllModels = () => mlApi.post('/ml/train-all');
export const checkTrainingReadiness = () => mlApi.get('/ml/training/readiness');
export const clearModelCache = () => mlApi.post('/ml/cache/clear');
