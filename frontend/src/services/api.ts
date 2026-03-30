import axios from 'axios';

export const backendApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
});

export const mlApi = axios.create({
  baseURL: import.meta.env.VITE_ML_URL || 'http://localhost:8001',
  timeout: 60000,
});

// --------------- Request / Response Logging ---------------

const TAG_STYLE = 'color:#6366f1;font-weight:bold';
const OK_STYLE = 'color:#22c55e;font-weight:bold';
const ERR_STYLE = 'color:#ef4444;font-weight:bold';
const DIM_STYLE = 'color:#9ca3af';

function attachLogging(instance: ReturnType<typeof axios.create>, label: string) {
  instance.interceptors.request.use((config) => {
    const method = (config.method ?? 'GET').toUpperCase();
    console.log(
      `%c[${label}] %c>>> ${method} %c${config.url}`,
      TAG_STYLE, DIM_STYLE, 'color:inherit',
      config.params ?? '',
    );
    (config as any).__startTime = performance.now();
    return config;
  });

  instance.interceptors.response.use(
    (response) => {
      const ms = Math.round(performance.now() - ((response.config as any).__startTime ?? 0));
      console.log(
        `%c[${label}] %c<<< ${response.status} %c${response.config.url} %c${ms}ms`,
        TAG_STYLE, OK_STYLE, 'color:inherit', DIM_STYLE,
      );
      return response;
    },
    (error) => {
      const ms = error.config
        ? Math.round(performance.now() - ((error.config as any).__startTime ?? 0))
        : 0;
      const status = error.response?.status ?? 'NETWORK_ERROR';
      console.error(
        `%c[${label}] %c!!! ${status} %c${error.config?.url ?? '?'} %c${ms}ms`,
        TAG_STYLE, ERR_STYLE, 'color:inherit', DIM_STYLE,
        error.response?.data ?? error.message,
      );
      return Promise.reject(error);
    },
  );
}

attachLogging(backendApi, 'API');
attachLogging(mlApi, 'ML');
