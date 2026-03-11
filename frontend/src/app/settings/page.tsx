'use client';

import { useEffect, useState } from 'react';
import { getSettings, type SettingsData } from '@/lib/api';
import styles from './page.module.css';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const res = await getSettings();
      if (res.data) setSettings(res.data);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) return <div className="loading">Loading configuration...</div>;
  if (!settings) return <div className="error">Failed to load settings</div>;

  return (
    <div className="page-container fade-in">
      <div className={styles.header}>
        <h1 className="page-title">SYSTEM CONFIGURATION</h1>
        <div className={styles.modeBadge}>{settings.mode.toUpperCase()} MODE</div>
      </div>

      <div className="grid-2">
        {/* AI Models Card */}
        <div className="card">
          <div className="card-title">🧠 AI Neural Core</div>
          <div className={styles.configGroup}>
            <div className={styles.item}>
              <label>Primary Model (General)</label>
              <div className={styles.value}>{settings.ai_models.primary}</div>
            </div>
            <div className={styles.item}>
              <label>Secondary Model (Fallback)</label>
              <div className={styles.value}>{settings.ai_models.secondary}</div>
            </div>
            <div className={styles.item}>
              <label>Research Model (News)</label>
              <div className={styles.value}>{settings.ai_models.news}</div>
            </div>
          </div>
        </div>

        {/* Risk Management Card */}
        <div className="card">
          <div className="card-title">🛡 Risk Protocols</div>
          <div className={styles.configGroup}>
            <div className={styles.item}>
              <label>Max Drawdown Limit</label>
              <div className={`${styles.value} num-negative`}>-{settings.risk.max_drawdown}%</div>
            </div>
            <div className={styles.item}>
              <label>Risk Per Trade</label>
              <div className={styles.value}>{settings.risk.risk_per_trade}%</div>
            </div>
            <div className={styles.item}>
              <label>Max Concurrent Positions</label>
              <div className={styles.value}>{settings.risk.max_positions}</div>
            </div>
          </div>
        </div>

        {/* System Params Card */}
        <div className="card">
          <div className="card-title">⚙ System Parameters</div>
          <div className={styles.configGroup}>
            <div className={styles.item}>
              <label>Cycle Interval</label>
              <div className={styles.value}>{settings.system.cycle_interval}s</div>
            </div>
            <div className={styles.item}>
              <label>Auto-Start on Boot</label>
              <div className={styles.value}>
                <span className={settings.system.auto_start ? styles.on : styles.off}>
                  {settings.system.auto_start ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Environment Info */}
        <div className="card">
          <div className="card-title">ℹ Environment</div>
          <div className={styles.configGroup}>
            <div className={styles.item}>
              <label>Backend URL</label>
              <div className={styles.mono}>http://localhost:8000</div>
            </div>
            <div className={styles.item}>
              <label>Frontend Build</label>
              <div className={styles.mono}>v1.0.0 (Phase 5)</div>
            </div>
            <div className={styles.item}>
              <label>Status</label>
              <div className="num-positive">OPERATIONAL</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
