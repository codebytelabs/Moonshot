/**
 * API client for Moonshot Trading Bot backend.
 * Connects to FastAPI running on port 8000.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiResponse<T> {
  data: T | null;
  error: string | null;
}

async function request<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    });
    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }
    const data = await res.json();
    return { data, error: null };
  } catch (err) {
    return { data: null, error: (err as Error).message };
  }
}

// ── API Methods ───────────────────────────────────────────────

export async function getHealth() {
  return request<{ status: string; uptime: number; mode: string }>("/health");
}

export async function getStatus() {
  return request<BotStatus>("/status");
}

export async function getPositions() {
  const res = await request<{ positions: Position[] }>("/positions");
  if (res.data && res.data.positions) {
    return { data: res.data.positions, error: null };
  }
  return { data: [], error: res.error };
}

export async function getTrades() {
  const res = await request<{ trades: Trade[] }>("/trades");
  if (res.data && res.data.trades) {
    return { data: res.data.trades, error: null };
  }
  return { data: [], error: res.error };
}

export async function getPerformance() {
  return request<PerformanceData>("/performance");
}

export async function getMetrics() {
  return request<MetricsData>("/metrics");
}

export async function sendChat(message: string) {
  return request<{ reply: string }>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// ── Types ─────────────────────────────────────────────────────

export interface BotStatus {
  mode: string;
  health: {
    equity: number;
    peak_equity: number;
    drawdown_pct: number;
    total_exposure_pct: number;
    open_positions: number;
    max_positions: number;
    daily_pnl: number;
    daily_loss_pct: number;
    recommended_mode: string;
    can_trade: boolean;
  };
  total_trades: number;
  win_rate: number;
  recent_events: any[];
  // Optional fields for WebSocket updates
  cycle?: number;
  uptime_seconds?: number;
  current_mode?: string;
  equity_usd?: number; // Keep for legacy/WS compatibility if needed
  drawdown_pct?: number; // Keep for legacy/WS compatibility if needed
  candidates_found?: number;
  setups_passed?: number;
  decisions_made?: number;
}

export interface Position {
  id: string;
  symbol: string;
  side: string;
  status: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  notional_usd: number;
  unrealized_pnl: number;
  pnl_pct: number;
  r_multiple: number;
  stop_loss: number;
  take_profit: number;
  opened_at: string;
}

export interface Trade {
  id: string;
  position_id: string;
  symbol: string;
  side: string;
  price: number;
  quantity: number;
  notional_usd: number;
  trade_type: string;
  pnl: number;
  r_multiple: number;
  created_at: string;
}

export interface PerformanceData {
  equity_usd: number;
  total_pnl: number;
  win_rate: number;
  avg_r: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  avg_holding_minutes: number;
  equity_history: { timestamp: string; equity: number }[];
}

export interface MetricsData {
  cycle: number;
  pipeline: {
    stage: string;
    status: string;
    duration_ms: number;
    items: number;
  }[];
  health: {
    equity: number;
    drawdown_pct: number;
    recommended_mode: string;
    open_positions: number;
  };
}

export interface Alert {
  id: string;
  type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  timestamp: string;
  symbol?: string;
}

export interface WsMessage {
  type: string;
  cycle?: number;
  mode?: string;
  pipeline?: MetricsData["pipeline"];
  positions?: Position[];
  alerts?: Alert[];
  equity?: number;
  drawdown_pct?: number;
  candidates?: number;
  setups?: number;
}

export interface SettingsData {
  mode: string;
  ai_models: {
    primary: string;
    secondary: string;
    news: string;
  };
  risk: {
    max_drawdown: number;
    risk_per_trade: number;
    max_positions: number;
  };
  system: {
    cycle_interval: number;
    auto_start: boolean;
  };
}

export async function getSettings() {
  return request<SettingsData>("/settings");
}
