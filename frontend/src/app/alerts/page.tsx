'use client';

import { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import DataRain from '@/components/DataRain';
import { useWebSocket } from '@/lib/useWebSocket';
import { getStatus, type BotStatus, type Alert } from '@/lib/api';
import { severityClass } from '@/lib/utils';
import styles from './alerts.module.css';

export default function AlertsPage() {
  const { isConnected, messages: wsMessages } = useWebSocket();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [filter, setFilter] = useState<'all' | 'info' | 'warning' | 'critical'>('all');

  const fetchData = useCallback(async () => {
    const statusRes = await getStatus();
    if (statusRes.data) setStatus(statusRes.data);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Collect alerts from WebSocket
  useEffect(() => {
    for (const msg of wsMessages) {
      if (msg.alerts) {
        setAlerts((prev) => {
          const ids = new Set(prev.map((a) => a.id));
          const newAlerts = msg.alerts!.filter((a) => !ids.has(a.id));
          return [...newAlerts, ...prev].slice(0, 200);
        });
      }
    }
  }, [wsMessages]);

  const filtered = alerts.filter((a) => filter === 'all' || a.severity === filter);

  const counts = {
    all: alerts.length,
    info: alerts.filter((a) => a.severity === 'info').length,
    warning: alerts.filter((a) => a.severity === 'warning').length,
    critical: alerts.filter((a) => a.severity === 'critical').length,
  };

  return (
    <div className="app-container">
      <DataRain />
      <Sidebar />
      <Header wsConnected={isConnected} cycle={status?.cycle} mode={status?.current_mode} equity={status?.equity_usd} />
      <main className="main-content">
        <div className={styles.pageHeader}>
          <h1>⚡ Alerts</h1>
          <div className={styles.filters}>
            {(['all', 'info', 'warning', 'critical'] as const).map((f) => (
              <button
                key={f}
                className={`btn ${filter === f ? 'btn-primary' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f.toUpperCase()} ({counts[f]})
              </button>
            ))}
          </div>
        </div>

        {/* Alert Stats */}
        <div className={`grid-3 ${styles.statsRow}`}>
          <div className="card fade-in">
            <div className="card-title">Total Alerts</div>
            <div className="card-value">{alerts.length}</div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.05s' }}>
            <div className="card-title">⚠ Warnings</div>
            <div className="card-value" style={{ color: 'var(--orange)' }}>{counts.warning}</div>
          </div>
          <div className="card fade-in" style={{ animationDelay: '0.1s' }}>
            <div className="card-title">🔴 Critical</div>
            <div className="card-value" style={{ color: 'var(--red)' }}>{counts.critical}</div>
          </div>
        </div>

        {/* Alert Feed */}
        <div className="card fade-in" style={{ animationDelay: '0.15s' }}>
          <div className="card-title">Live Feed</div>
          {filtered.length === 0 ? (
            <div className={styles.empty}>
              <span className={styles.emptyIcon}>⚡</span>
              <span>No {filter !== 'all' ? filter : ''} alerts</span>
              <span className={styles.emptyHint}>
                {alerts.length === 0
                  ? 'Alerts will appear when the bot detects events'
                  : 'Try changing the filter'}
              </span>
            </div>
          ) : (
            <div className={styles.alertList}>
              {filtered.map((alert, i) => (
                <div key={alert.id || i} className={`${styles.alertItem} ${styles[alert.severity]}`}>
                  <div className={styles.alertLeft}>
                    <span className={`badge ${severityClass(alert.severity)}`}>
                      {alert.severity.toUpperCase()}
                    </span>
                    <span className={styles.alertType}>{alert.type}</span>
                  </div>
                  <div className={styles.alertContent}>
                    <span className={styles.alertMessage}>{alert.message}</span>
                    {alert.symbol && (
                      <span className={styles.alertSymbol}>{alert.symbol}</span>
                    )}
                  </div>
                  <span className={styles.alertTime}>
                    {alert.timestamp
                      ? new Date(alert.timestamp).toLocaleTimeString('en-US', { hour12: false })
                      : '—'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
