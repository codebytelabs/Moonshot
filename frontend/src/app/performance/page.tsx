'use client';

import { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import DataRain from '@/components/DataRain';
import { useWebSocket } from '@/lib/useWebSocket';
import { getPerformance, getStatus, type PerformanceData, type BotStatus } from '@/lib/api';
import { formatUsd, formatPct, pnlClass } from '@/lib/utils';
import styles from './performance.module.css';

export default function PerformancePage() {
  const { isConnected } = useWebSocket();
  const [perf, setPerf] = useState<PerformanceData | null>(null);
  const [status, setStatus] = useState<BotStatus | null>(null);

  const fetchData = useCallback(async () => {
    const [perfRes, statusRes] = await Promise.all([getPerformance(), getStatus()]);
    if (perfRes.data) setPerf(perfRes.data);
    if (statusRes.data) setStatus(statusRes.data);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="app-container">
      <DataRain />
      <Sidebar />
      <Header wsConnected={isConnected} cycle={status?.cycle} mode={status?.current_mode} equity={status?.equity_usd} />
      <main className="main-content">
        <h1 style={{ marginBottom: 'var(--gap-lg)' }}>◈ Performance</h1>

        {/* Main Metrics */}
        <div className={`grid-3 ${styles.metricsRow}`}>
          <div className="card fade-in">
            <div className="card-title">Portfolio Equity</div>
            <div className="card-value">{formatUsd(perf?.equity_usd ?? status?.equity_usd ?? 10000)}</div>
            <div className="gauge">
              <div className="gauge-fill gauge-fill-green" style={{ width: '100%' }} />
            </div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.05s' }}>
            <div className="card-title">Total Realized P&L</div>
            <div className={`card-value ${pnlClass(perf?.total_pnl ?? 0)}`}>
              {(perf?.total_pnl ?? 0) >= 0 ? '+' : ''}{formatUsd(perf?.total_pnl ?? 0)}
            </div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.1s' }}>
            <div className="card-title">Max Drawdown</div>
            <div className={`card-value num-negative`}>
              {formatPct(perf?.max_drawdown_pct ?? 0)}
            </div>
            <div className="gauge">
              <div
                className="gauge-fill gauge-fill-red"
                style={{ width: `${Math.min((perf?.max_drawdown_pct ?? 0) * 100 * 5, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Trading Stats */}
        <div className={`grid-4 ${styles.statsRow}`}>
          <GaugeStat
            label="Win Rate"
            value={`${((perf?.win_rate ?? 0) * 100).toFixed(0)}%`}
            pct={perf?.win_rate ?? 0}
            color={perf?.win_rate ?? 0 >= 0.5 ? 'green' : 'red'}
            delay="0.15s"
          />
          <GaugeStat
            label="Sharpe Ratio"
            value={(perf?.sharpe_ratio ?? 0).toFixed(2)}
            pct={Math.min((perf?.sharpe_ratio ?? 0) / 3, 1)}
            color="cyan"
            delay="0.2s"
          />
          <GaugeStat
            label="Avg R-Multiple"
            value={`${(perf?.avg_r ?? 0).toFixed(2)}R`}
            pct={Math.min(Math.max((perf?.avg_r ?? 0) + 1, 0) / 4, 1)}
            color={(perf?.avg_r ?? 0) > 0 ? 'green' : 'red'}
            delay="0.25s"
          />
          <GaugeStat
            label="Avg Hold Time"
            value={`${(perf?.avg_holding_minutes ?? 0).toFixed(0)}m`}
            pct={Math.min((perf?.avg_holding_minutes ?? 0) / 120, 1)}
            color="cyan"
            delay="0.3s"
          />
        </div>

        {/* Trade Breakdown */}
        <div className={`grid-2 ${styles.breakdownRow}`}>
          <div className="card fade-in" style={{ animationDelay: '0.35s' }}>
            <div className="card-title">Trade Breakdown</div>
            <div className={styles.breakdown}>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Total Trades</span>
                <span className={styles.breakdownValue}>{perf?.total_trades ?? 0}</span>
              </div>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Winners</span>
                <span className={`${styles.breakdownValue} num-positive`}>{perf?.winning_trades ?? 0}</span>
              </div>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Losers</span>
                <span className={`${styles.breakdownValue} num-negative`}>{perf?.losing_trades ?? 0}</span>
              </div>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Win/Loss Ratio</span>
                <span className={styles.breakdownValue}>
                  {(perf?.losing_trades ?? 0) > 0
                    ? ((perf?.winning_trades ?? 0) / (perf?.losing_trades ?? 1)).toFixed(2)
                    : '∞'}
                </span>
              </div>
            </div>
          </div>

          <div className="card fade-in" style={{ animationDelay: '0.4s' }}>
            <div className="card-title">Risk Health</div>
            <div className={styles.breakdown}>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Current Mode</span>
                <span className={`badge ${status?.current_mode === 'normal' ? 'badge-online' : 'badge-warning'}`}>
                  {status?.current_mode?.toUpperCase() ?? 'NORMAL'}
                </span>
              </div>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Drawdown</span>
                <span className={`${styles.breakdownValue} ${(status?.drawdown_pct ?? 0) > 0.05 ? 'num-negative' : 'num-positive'}`}>
                  {formatPct(status?.drawdown_pct ?? 0)}
                </span>
              </div>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Open Positions</span>
                <span className={styles.breakdownValue}>{status?.open_positions ?? 0}/5</span>
              </div>
              <div className={styles.breakdownItem}>
                <span className={styles.breakdownLabel}>Equity</span>
                <span className={styles.breakdownValue}>{formatUsd(status?.equity_usd ?? 10000)}</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function GaugeStat({ label, value, pct, color, delay }: {
  label: string; value: string; pct: number; color: string; delay: string;
}) {
  const fillClass = color === 'green' ? 'gauge-fill-green'
    : color === 'red' ? 'gauge-fill-red'
    : 'gauge-fill-cyan';

  return (
    <div className="card fade-in" style={{ animationDelay: delay }}>
      <div className="card-title">{label}</div>
      <div className={`card-value ${color === 'red' ? 'num-negative' : ''}`} style={{ fontSize: '1.4rem' }}>
        {value}
      </div>
      <div className="gauge">
        <div className={`gauge-fill ${fillClass}`} style={{ width: `${pct * 100}%` }} />
      </div>
    </div>
  );
}
