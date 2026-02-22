import { backendApi } from './api';

export const getFleetSummary = () => backendApi.get('/dashboard/summary');
export const getDailyTrend = (days = 30) => backendApi.get(`/dashboard/daily-trend?days=${days}`);
export const getTopDrivers = (limit = 10) => backendApi.get(`/dashboard/top-drivers?limit=${limit}`);
export const getRouteHeatmap = (limit = 20) => backendApi.get(`/dashboard/route-heatmap?limit=${limit}`);
export const getRecentAlerts = (limit = 10) => backendApi.get(`/dashboard/alerts/recent?limit=${limit}`);
