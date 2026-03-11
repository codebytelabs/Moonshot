'use client';

import { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import DataRain from '@/components/DataRain';
import { useWebSocket } from '@/lib/useWebSocket';
import { getPositions, getStatus, type Position, type BotStatus } from '@/lib/api';
import { formatUsd, formatPct, pnlClass, timeAgo, formatPrice } from '@/lib/utils';
import styles from './positions.module.css';

export default function PositionsPage() {
  const { isConnected, lastMessage } = useWebSocket();
  const [positions, setPositions] = useState<Position[]>([]);
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all');

  const fetchData = useCallback(async () => {
    const [posRes, statusRes] = await Promise.all([getPositions(), getStatus()]);
    if (posRes.data) setPositions(posRes.data);
    if (statusRes.data) setStatus(statusRes.data);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    if (lastMessage?.positions) setPositions(lastMessage.positions);
  }, [lastMessage]);

  const filtered = positions.filter((p) => {
    if (filter === 'open') return p.status === 'open';
    if (filter === 'closed') return p.status === 'closed';
    return true;
  });

  const totalUnrealized = filtered.filter((p) => p.status === 'open').reduce((s, p) => s + (p.unrealized_pnl || 0), 0);

  return (
    <div className="app-container">
      <DataRain />
      <Sidebar />
      <Header wsConnected={isConnected} cycle={status?.cycle} mode={status?.current_mode} equity={status?.equity_usd} />
      <main className="main-content">
        <div className={styles.pageHeader}>
          <h1>⊞ Positions</h1>
          <div className={styles.filters}>
            {(['all', 'open', 'closed'] as const).map((f) => (
              <button
                key={f}
                className={`btn ${filter === f ? 'btn-primary' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Summary Cards */}
        <div className={`grid-3 ${styles.summary}`}>
          <div className="card fade-in">
            <div className="card-title">Open</div>
            <div className="card-value">{positions.filter((p) => p.status === 'open').length}</div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.05s' }}>
            <div className="card-title">Total Unrealized</div>
            <div className={`card-value ${pnlClass(totalUnrealized)}`}>
              {totalUnrealized >= 0 ? '+' : ''}{formatUsd(totalUnrealized)}
            </div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.1s' }}>
            <div className="card-title">Total Positions</div>
            <div className="card-value">{positions.length}</div>
          </div>
        </div>

        {/* Positions Table */}
        <div className="card fade-in" style={{ animationDelay: '0.15s' }}>
          {filtered.length === 0 ? (
            <div className={styles.empty}>
              <span className={styles.emptyIcon}>◇</span>
              <span>No {filter !== 'all' ? filter : ''} positions</span>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Status</th>
                    <th>Entry</th>
                    <th>Current</th>
                    <th>Size (USD)</th>
                    <th>P&L</th>
                    <th>P&L %</th>
                    <th>R-Multiple</th>
                    <th>Stop Loss</th>
                    <th>Opened</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((pos) => (
                    <tr key={pos.id} className={styles.posRow}>
                      <td>
                        <strong className={styles.symbol}>{pos.symbol}</strong>
                      </td>
                      <td>
                        <span className={`badge ${pos.side === 'long' ? 'badge-enter' : 'badge-exit'}`}>
                          {pos.side.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${pos.status === 'open' ? 'badge-online' : 'badge-offline'}`}>
                          {pos.status.toUpperCase()}
                        </span>
                      </td>
                      <td>{formatPrice(pos.entry_price)}</td>
                      <td>{formatPrice(pos.current_price)}</td>
                      <td>{formatUsd(pos.notional_usd)}</td>
                      <td className={pnlClass(pos.unrealized_pnl)}>
                        {pos.unrealized_pnl >= 0 ? '+' : ''}{formatUsd(pos.unrealized_pnl)}
                      </td>
                      <td className={pnlClass(pos.pnl_pct)}>
                        {formatPct(pos.pnl_pct || 0)}
                      </td>
                      <td className={pnlClass(pos.r_multiple)}>
                        {pos.r_multiple?.toFixed(2)}R
                      </td>
                      <td>{pos.stop_loss ? formatPrice(pos.stop_loss) : '—'}</td>
                      <td className={styles.timeCell}>{pos.opened_at ? timeAgo(pos.opened_at) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
