'use client';

import { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import DataRain from '@/components/DataRain';
import { useWebSocket } from '@/lib/useWebSocket';
import { getTrades, getStatus, type Trade, type BotStatus } from '@/lib/api';
import { formatUsd, pnlClass, formatPrice } from '@/lib/utils';
import styles from './trades.module.css';

export default function TradesPage() {
  const { isConnected } = useWebSocket();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [status, setStatus] = useState<BotStatus | null>(null);

  const fetchData = useCallback(async () => {
    const [tradesRes, statusRes] = await Promise.all([getTrades(), getStatus()]);
    if (tradesRes.data) setTrades(tradesRes.data);
    if (statusRes.data) setStatus(statusRes.data);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const totalPnl = trades.reduce((s, t) => s + (t.pnl || 0), 0);
  const winners = trades.filter((t) => (t.pnl || 0) > 0).length;
  const losers = trades.filter((t) => (t.pnl || 0) < 0).length;
  const winRate = trades.length > 0 ? winners / trades.length : 0;

  return (
    <div className="app-container">
      <DataRain />
      <Sidebar />
      <Header wsConnected={isConnected} cycle={status?.cycle} mode={status?.current_mode} equity={status?.equity_usd} />
      <main className="main-content">
        <h1 style={{ marginBottom: 'var(--gap-lg)' }}>⇄ Trade History</h1>

        <div className={`grid-4 ${styles.summary}`}>
          <div className="card fade-in">
            <div className="card-title">Total Trades</div>
            <div className="card-value">{trades.length}</div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.05s' }}>
            <div className="card-title">Total P&L</div>
            <div className={`card-value ${pnlClass(totalPnl)}`}>
              {totalPnl >= 0 ? '+' : ''}{formatUsd(totalPnl)}
            </div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.1s' }}>
            <div className="card-title">Win Rate</div>
            <div className={`card-value ${winRate >= 0.5 ? 'num-positive' : 'num-negative'}`}>
              {(winRate * 100).toFixed(0)}%
            </div>
            <div className={styles.winLoss}>
              <span className="num-positive">{winners}W</span>
              <span className={styles.separator}>/</span>
              <span className="num-negative">{losers}L</span>
            </div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.15s' }}>
            <div className="card-title">Avg R-Multiple</div>
            <div className={`card-value ${pnlClass(trades.length > 0 ? trades.reduce((s, t) => s + (t.r_multiple || 0), 0) / trades.length : 0)}`}>
              {trades.length > 0
                ? (trades.reduce((s, t) => s + (t.r_multiple || 0), 0) / trades.length).toFixed(2)
                : '0.00'}R
            </div>
          </div>
        </div>

        <div className="card fade-in" style={{ animationDelay: '0.2s' }}>
          {trades.length === 0 ? (
            <div className={styles.empty}>
              <span className={styles.emptyIcon}>⇄</span>
              <span>No trades yet</span>
              <span className={styles.emptyHint}>Trades will appear when the bot executes entries and exits</span>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th>Side</th>
                    <th>Price</th>
                    <th>Quantity</th>
                    <th>Notional</th>
                    <th>P&L</th>
                    <th>R</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id}>
                      <td className={styles.timeCell}>
                        {trade.created_at
                          ? new Date(trade.created_at).toLocaleString('en-US', {
                              month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                            })
                          : '—'}
                      </td>
                      <td><strong className={styles.symbol}>{trade.symbol}</strong></td>
                      <td>
                        <span className={`badge ${trade.trade_type === 'entry' ? 'badge-enter' : 'badge-exit'}`}>
                          {trade.trade_type.toUpperCase()}
                        </span>
                      </td>
                      <td>{trade.side.toUpperCase()}</td>
                      <td>{formatPrice(trade.price)}</td>
                      <td>{trade.quantity.toFixed(4)}</td>
                      <td>{formatUsd(trade.notional_usd)}</td>
                      <td className={pnlClass(trade.pnl || 0)}>
                        {trade.pnl != null ? `${trade.pnl >= 0 ? '+' : ''}${formatUsd(trade.pnl)}` : '—'}
                      </td>
                      <td className={pnlClass(trade.r_multiple || 0)}>
                        {trade.r_multiple != null ? `${trade.r_multiple.toFixed(2)}R` : '—'}
                      </td>
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
