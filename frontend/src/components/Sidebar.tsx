'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: '◉' },
  { href: '/positions', label: 'Positions', icon: '⊞' },
  { href: '/trades', label: 'Trades', icon: '⇄' },
  { href: '/performance', label: 'Performance', icon: '◈' },
  { href: '/chat', label: 'BigBrother', icon: '⬡' },
  { href: '/alerts', label: 'Alerts', icon: '⚡' },
  { href: '/settings', label: 'Settings', icon: '⚙' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className={styles.logo}>
        <div className={styles.logoIcon}>◬</div>
        <div className={styles.logoText}>
          <span className={styles.logoTitle}>MOONSHOT</span>
          <span className={styles.logoSub}>TRADING BOT</span>
        </div>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`${styles.navItem} ${pathname === item.href ? styles.active : ''}`}
          >
            <span className={styles.navIcon}>{item.icon}</span>
            <span className={styles.navLabel}>{item.label}</span>
            {pathname === item.href && <span className={styles.activeBar} />}
          </Link>
        ))}
      </nav>

      <div className={styles.footer}>
        <div className={styles.version}>v1.0.0 — Phase 5</div>
        <div className={styles.indicator}>
          <span className="pulse-dot" />
          <span className={styles.indicatorText}>SYSTEM ONLINE</span>
        </div>
      </div>
    </aside>
  );
}
