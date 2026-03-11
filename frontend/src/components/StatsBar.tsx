"use client";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Wallet, Target, BarChart3, Layers } from "lucide-react";

interface DashboardData {
  portfolio_value: number;
  active_positions: number;
  total_trades: number;
  total_alpha_hits: number;
  swarm_active: boolean;
  wallets: { evm: string; sol: string };
}

function StatCard({ label, value, sub, icon, color }: { label: string; value: string; sub?: string; icon: React.ReactNode; color: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-white/[0.02] border border-cyan-900/15 px-3 py-2 flex items-center gap-3 hover:border-cyan-500/30 transition-all group"
    >
      <div className="p-1.5 border border-current/20 shrink-0" style={{ color }}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">{label}</div>
        <div className="font-mono text-sm font-bold text-white">{value}</div>
        {sub && <div className="text-[9px] font-mono" style={{ color }}>{sub}</div>}
      </div>
    </motion.div>
  );
}

export default function StatsBar({ data }: { data: DashboardData | null }) {
  if (!data) return null;

  const pnl = ((data.portfolio_value - 10000) / 10000) * 100;

  return (
    <div className="grid grid-cols-5 gap-2" data-testid="stats-bar">
      <StatCard
        label="Portfolio NAV"
        value={`$${data.portfolio_value.toLocaleString()}`}
        sub={`${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}% all-time`}
        icon={<Wallet size={14} />}
        color={pnl >= 0 ? "#39FF14" : "#FF003C"}
      />
      <StatCard
        label="Active Positions"
        value={`${data.active_positions}`}
        icon={<Target size={14} />}
        color="#00F3FF"
      />
      <StatCard
        label="Total Trades"
        value={`${data.total_trades}`}
        icon={<BarChart3 size={14} />}
        color="#FFD700"
      />
      <StatCard
        label="Alpha Hits"
        value={`${data.total_alpha_hits}`}
        icon={<TrendingUp size={14} />}
        color="#9945FF"
      />
      <StatCard
        label="Swarm"
        value={data.swarm_active ? "ONLINE" : "OFFLINE"}
        icon={<Layers size={14} />}
        color={data.swarm_active ? "#39FF14" : "#FF003C"}
      />
    </div>
  );
}
