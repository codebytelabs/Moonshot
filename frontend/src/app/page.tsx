'use client';

import { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import DataRain from '@/components/DataRain';
import PipelineVisualizer from '@/components/PipelineVisualizer';
import { useWebSocket } from '@/lib/useWebSocket';
import { getStatus, getPositions, getPerformance, type BotStatus, type Position, type PerformanceData } from '@/lib/api';
import { formatUsd, formatPct, pnlClass } from '@/lib/utils';
import styles from './page.module.css';

export default function Dashboard() {
  const { isConnected, lastMessage } = useWebSocket();
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [perf, setPerf] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);

  // Pipeline stages derived from ws messages or mock
  type PipelineStage = {
    name: string;
    icon: string;
    status: 'idle' | 'running' | 'done' | 'error';
    items?: number;
    duration_ms?: number;
  };

  const [pipelineStages, setPipelineStages] = useState<PipelineStage[]>([
    { name: 'Watcher', icon: '👁', status: 'idle' },
    { name: 'Analyzer', icon: '📊', status: 'idle' },
    { name: 'Context', icon: '🌐', status: 'idle' },
    { name: 'Bayesian', icon: '🧠', status: 'idle' },
    { name: 'Risk', icon: '🛡', status: 'idle' },
    { name: 'Execute', icon: '⚡', status: 'idle' },
    { name: 'BigBro', icon: '🔮', status: 'idle' },
  ]);

  const fetchData = useCallback(async () => {
    const [statusRes, posRes, perfRes] = await Promise.all([
      getStatus(),
      getPositions(),
      getPerformance(),
    ]);
    if (statusRes.data) setStatus(statusRes.data);
    if (posRes.data) setPositions(posRes.data);
    if (perfRes.data) setPerf(perfRes.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Update from WS messages
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.pipeline) {
      const mapped = lastMessage.pipeline.map((p) => ({
        name: p.stage,
        icon: { Watcher: '👁', Analyzer: '📊', Context: '🌐', Bayesian: '🧠', Risk: '🛡', Execute: '⚡', BigBro: '🔮' }[p.stage] || '●',
        status: p.status as 'idle' | 'running' | 'done' | 'error',
        items: p.items,
        duration_ms: p.duration_ms,
      }));
      setPipelineStages(mapped);
    }
    if (lastMessage.equity && status) {
      setStatus({ ...status, equity_usd: lastMessage.equity });
    }
    if (lastMessage.positions) {
      setPositions(lastMessage.positions);
    }
  }, [lastMessage, status]);

  const equity = status?.health?.equity ?? status?.equity_usd ?? 10000;
  const drawdown = status?.health?.drawdown_pct ?? status?.drawdown_pct ?? 0;
  const openPositions = positions.filter((p) => p.status === 'open');
  const totalPnl = openPositions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);

  return (
    <div className="app-container">
      <DataRain />
      <Sidebar />
      <Header
        wsConnected={isConnected}
        cycle={status?.cycle}
        mode={status?.current_mode}
        equity={equity}
      />

      <main className="main-content">
        {/* ── KPI Row ──────────────────────────────── */}
        <div className={`grid-4 ${styles.kpiRow}`}>
          <div className="card fade-in">
            <div className="card-title">◉ Equity</div>
            <div className="card-value">{formatUsd(equity)}</div>
            <div className={styles.kpiSub}>Paper Trading</div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.05s' }}>
            <div className="card-title">⊞ Open Positions</div>
            <div className="card-value">{openPositions.length}</div>
            <div className={styles.kpiSub}>/ 5 max</div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.1s' }}>
            <div className="card-title">◈ Unrealized P&L</div>
            <div className={`card-value ${pnlClass(totalPnl)}`}>
              {totalPnl >= 0 ? '+' : ''}{formatUsd(totalPnl)}
            </div>
            <div className={styles.kpiSub}>Across active</div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.15s' }}>
            <div className="card-title">⚡ Drawdown</div>
            <div className={`card-value ${drawdown > 0.05 ? 'num-negative' : 'num-positive'}`}>
              {formatPct(drawdown)}
            </div>
            <div className="gauge">
              <div
                className={`gauge-fill ${drawdown > 0.05 ? 'gauge-fill-red' : 'gauge-fill-green'}`}
                style={{ width: `${Math.min(drawdown * 100 * 5, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* ── Pipeline ─────────────────────────────── */}
        <div className={`card ${styles.pipelineCard} fade-in`} style={{ animationDelay: '0.2s' }}>
          <div className="card-title">⬡ Agent Pipeline</div>
          <PipelineVisualizer stages={pipelineStages} />
        </div>

        {/* ── Two Column: Positions + Activity ─────── */}
        <div className={`grid-2 ${styles.bottomRow}`}>
          {/* Active Positions */}
          <div className="card fade-in" style={{ animationDelay: '0.25s' }}>
            <div className="card-title">⊞ Active Positions</div>
            {openPositions.length === 0 ? (
              <div className={styles.empty}>
                <span className={styles.emptyIcon}>◇</span>
                <span>No open positions</span>
                <span className={styles.emptyHint}>Bot is scanning for opportunities...</span>
              </div>
            ) : (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Entry</th>
                      <th>Current</th>
                      <th>P&L</th>
                      <th>R</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openPositions.map((pos) => (
                      <tr key={pos.id}>
                        <td><strong>{pos.symbol}</strong></td>
                        <td>${pos.entry_price.toFixed(4)}</td>
                        <td>${pos.current_price.toFixed(4)}</td>
                        <td className={pnlClass(pos.unrealized_pnl)}>
                          {pos.unrealized_pnl >= 0 ? '+' : ''}{formatUsd(pos.unrealized_pnl)}
                        </td>
                        <td className={pnlClass(pos.r_multiple)}>{pos.r_multiple?.toFixed(1)}R</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Live Activity Feed */}
          <div className="card fade-in" style={{ animationDelay: '0.3s' }}>
            <div className="card-title">⚡ Live Activity</div>
            <div className={styles.activityFeed}>
              {status ? (
                <>
                  <ActivityLine icon="🔍" text={`Cycle #${status.cycle} — ${status.candidates_found} candidates scanned`} />
                  <ActivityLine icon="📊" text={`${status.setups_passed} setups passed analysis`} />
                  <ActivityLine icon="🧠" text={`${status.decisions_made} Bayesian decisions`} />
                  <ActivityLine icon="💰" text={`Equity: ${formatUsd(equity)} | Drawdown: ${formatPct(drawdown)}`} />
                  <ActivityLine icon="🛡" text={`Mode: ${status.current_mode?.toUpperCase() ?? 'NORMAL'}`} />
                  <ActivityLine icon="⏱" text={`Uptime: ${Math.floor((status.uptime_seconds || 0) / 60)}m`} />
                </>
              ) : loading ? (
                <div className={styles.empty}>
                  <span>Connecting to bot...</span>
                  <span className="cursor-blink" />
                </div>
              ) : (
                <div className={styles.empty}>
                  <span className={styles.emptyIcon}>⊘</span>
                  <span>Bot offline — start with <code>python -m src.main</code></span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Performance Summary ──────────────────── */}
        {perf && (
          <div className={`grid-4 ${styles.perfRow} fade-in`} style={{ animationDelay: '0.35s' }}>
            <div className="card">
              <div className="card-title">Win Rate</div>
              <div className={`card-value ${perf.win_rate > 0.5 ? 'num-positive' : 'num-negative'}`}>
                {(perf.win_rate * 100).toFixed(0)}%
              </div>
            </div>
            <div className="card">
              <div className="card-title">Avg R-Multiple</div>
              <div className={`card-value ${pnlClass(perf.avg_r)}`}>{perf.avg_r?.toFixed(2)}R</div>
            </div>
            <div className="card">
              <div className="card-title">Total Trades</div>
              <div className="card-value">{perf.total_trades}</div>
            </div>
            <div className="card">
              <div className="card-title">Sharpe Ratio</div>
              <div className={`card-value ${pnlClass(perf.sharpe_ratio)}`}>{perf.sharpe_ratio?.toFixed(2)}</div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function ActivityLine({ icon, text }: { icon: string; text: string }) {
  return (
    <div className={styles.activityLine}>
      <span className={styles.activityIcon}>{icon}</span>
      <span className={styles.activityText}>{text}</span>
    </div>
  );
}
