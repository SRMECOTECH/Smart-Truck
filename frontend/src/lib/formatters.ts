export function formatNumber(n: number | null | undefined): string {
  if (n == null) return '-';
  return n.toLocaleString('en-IN');
}

export function formatDuration(minutes: number | null | undefined): string {
  if (minutes == null) return '-';
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function formatDistance(km: number | null | undefined): string {
  if (km == null) return '-';
  return `${km.toLocaleString('en-IN', { maximumFractionDigits: 1 })} km`;
}

export function formatPercent(val: number | null | undefined): string {
  if (val == null) return '-';
  return `${val.toFixed(1)}%`;
}

export function formatSpeed(kmph: number | null | undefined): string {
  if (kmph == null) return '-';
  return `${kmph.toFixed(1)} km/h`;
}

export function formatDate(dt: string | null | undefined): string {
  if (!dt) return '-';
  try {
    return new Date(dt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return dt; }
}

export function formatDateTime(dt: string | null | undefined): string {
  if (!dt) return '-';
  try {
    return new Date(dt).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return dt; }
}
