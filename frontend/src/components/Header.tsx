'use client';

import { useEffect, useState } from 'react';
import styles from './Header.module.css';

interface HeaderProps {
  wsConnected: boolean;
  cycle?: number;
  mode?: string;
  equity?: number;
}

export default function Header({ wsConnected, cycle, mode, equity }: HeaderProps) {
  const [time, setTime] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString('en-US', { hour12: false }));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="header">
      <div className={styles.left}>
        <div className={styles.statusGroup}>
          <span className={`pulse-dot ${wsConnected ? '' : 'pulse-dot-red'}`} />
          <span className={styles.statusText}>
            {wsConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
        {mode && (
          <span className={`badge ${mode === 'normal' ? 'badge-online' : mode === 'cautious' ? 'badge-warning' : 'badge-exit'}`}>
            {mode.toUpperCase()}
          </span>
        )}
        {cycle !== undefined && (
          <span className={styles.cycle}>CYCLE #{cycle}</span>
        )}
      </div>

      <div className={styles.center}>
        <span className={styles.clock}>{time}</span>
      </div>

      <div className={styles.right}>
        {equity !== undefined && (
          <div className={styles.equityBox}>
            <span className={styles.equityLabel}>EQUITY</span>
            <span className={styles.equityValue}>
              ${equity.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
