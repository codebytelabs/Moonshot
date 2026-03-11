/**
 * Utility functions for the dashboard.
 */

export function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: value > 1000 ? 0 : 2,
  }).format(value);
}

export function formatPct(value: number, decimals = 1): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPrice(value: number): string {
  if (value > 1000) return formatUsd(value);
  if (value > 1) return `$${value.toFixed(2)}`;
  if (value > 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(6)}`;
}

export function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);

  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function pnlClass(value: number): string {
  if (value > 0) return 'num-positive';
  if (value < 0) return 'num-negative';
  return 'num-neutral';
}

export function severityClass(severity: string): string {
  switch (severity) {
    case 'critical': return 'badge-exit';
    case 'warning': return 'badge-warning';
    default: return 'badge-online';
  }
}
