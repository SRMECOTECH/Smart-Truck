import axios from 'axios';

export const backendApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
});

export const mlApi = axios.create({
  baseURL: import.meta.env.VITE_ML_URL || 'http://localhost:8001',
  timeout: 60000,
});
