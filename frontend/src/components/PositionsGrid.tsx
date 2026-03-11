"use client";
import { motion } from "framer-motion";

interface Position {
  id: string;
  symbol: string;
  chainId: string;
  side: string;
  entry_price: string;
  current_price: string;
  amount_usd: number;
  pnl_pct: number;
  status: string;
}

const CHAIN_BADGE: Record<string, string> = {
  ethereum: "bg-[#627EEA]/20 text-[#627EEA]",
  solana: "bg-[#9945FF]/20 text-[#9945FF]",
  base: "bg-[#0052FF]/20 text-[#0052FF]",
  bsc: "bg-[#F0B90B]/20 text-[#F0B90B]",
  polygon: "bg-[#8247E5]/20 text-[#8247E5]",
  arbitrum: "bg-[#12AAFF]/20 text-[#12AAFF]",
};

export default function PositionsGrid({ positions }: { positions: Position[] }) {
  return (
    <div className="cyber-panel h-full flex flex-col" data-testid="positions-grid">
      <div className="px-3 py-2 border-b border-cyan-900/30 flex items-center gap-2 shrink-0">
        <div className="w-2 h-2 rounded-full bg-[#FFD700] animate-pulse" />
        <h3 className="font-[Orbitron] text-xs tracking-[0.2em] uppercase neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
          Active Positions
        </h3>
        <span className="ml-auto text-[10px] font-mono text-slate-600">{positions.length} open</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {positions.map((pos, i) => (
          <motion.div
            key={pos.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="bg-white/[0.02] border border-cyan-900/20 px-3 py-2 flex items-center gap-3 hover:border-cyan-500/30 transition-colors"
            data-testid={`position-${pos.symbol}`}
          >
            <div className="flex flex-col min-w-[60px]">
              <span className="font-mono text-sm font-bold text-white">{pos.symbol}</span>
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded w-fit ${CHAIN_BADGE[pos.chainId] || "bg-slate-800 text-slate-400"}`}>
                {pos.chainId.toUpperCase().slice(0, 4)}
              </span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-[9px] text-slate-500 uppercase">Entry</span>
              <span className="font-mono text-[11px] text-slate-300">${pos.entry_price}</span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-[9px] text-slate-500 uppercase">Now</span>
              <span className="font-mono text-[11px] text-white">${pos.current_price}</span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-[9px] text-slate-500 uppercase">Size</span>
              <span className="font-mono text-[11px] text-slate-300">${pos.amount_usd}</span>
            </div>
            <div className="ml-auto flex flex-col items-end">
              <span className="text-[9px] text-slate-500 uppercase">PnL</span>
              <span className={`font-mono text-sm font-bold ${pos.pnl_pct >= 0 ? "neon-text-green" : "neon-text-magenta"}`}>
                {pos.pnl_pct >= 0 ? "+" : ""}{pos.pnl_pct.toFixed(1)}%
              </span>
            </div>
          </motion.div>
        ))}
        {positions.length === 0 && (
          <div className="text-center text-slate-600 font-mono text-xs py-6">No active positions</div>
        )}
      </div>
    </div>
  );
}
