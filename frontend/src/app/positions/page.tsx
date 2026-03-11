"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { apiFetch } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { ArrowUpRight, ArrowDownRight, ExternalLink } from "lucide-react";

interface Trade {
  id: string;
  symbol: string;
  chainId: string;
  side: string;
  price: string;
  amount_usd: number;
  status: string;
  route: string;
  timestamp: string;
  score: number;
  security: { verdict: string; risk_score: number };
}

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
  timestamp: string;
}

export default function PositionsPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [tab, setTab] = useState<"positions" | "trades">("positions");

  useEffect(() => {
    const load = async () => {
      try {
        const [t, p] = await Promise.all([
          apiFetch("/api/trades?limit=100"),
          apiFetch("/api/positions"),
        ]);
        setTrades(t);
        setPositions(p);
      } catch (e) {
        console.error(e);
      }
    };
    load();
  }, []);

  return (
    <div className="flex h-screen bg-[#050505]" data-testid="positions-page">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-12 border-b border-cyan-900/20 bg-[#0A0F0D]/80 backdrop-blur-sm flex items-center px-4 gap-4 shrink-0">
          <h1 className="font-[Orbitron] text-sm font-black tracking-[0.3em] uppercase neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
            POSITIONS
          </h1>
        </header>

        <div className="px-4 py-3 flex gap-2 shrink-0">
          <button
            onClick={() => setTab("positions")}
            data-testid="tab-positions"
            className={`px-4 py-1.5 text-xs font-mono tracking-wider border transition-all ${
              tab === "positions"
                ? "border-cyan-400/50 text-cyan-400 bg-cyan-400/10"
                : "border-cyan-900/20 text-slate-500 hover:text-slate-300"
            }`}
          >
            OPEN POSITIONS ({positions.length})
          </button>
          <button
            onClick={() => setTab("trades")}
            data-testid="tab-trades"
            className={`px-4 py-1.5 text-xs font-mono tracking-wider border transition-all ${
              tab === "trades"
                ? "border-cyan-400/50 text-cyan-400 bg-cyan-400/10"
                : "border-cyan-900/20 text-slate-500 hover:text-slate-300"
            }`}
          >
            TRADE HISTORY ({trades.length})
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {tab === "positions" && (
            <div className="space-y-2">
              {positions.map((pos, i) => (
                <motion.div
                  key={pos.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="cyber-panel px-4 py-3 flex items-center gap-6"
                  data-testid={`position-row-${pos.symbol}`}
                >
                  <div className="flex items-center gap-2 min-w-[100px]">
                    {pos.pnl_pct >= 0 ? (
                      <ArrowUpRight size={16} className="text-green-400" />
                    ) : (
                      <ArrowDownRight size={16} className="text-red-400" />
                    )}
                    <div>
                      <div className="font-mono text-sm font-bold text-white">{pos.symbol}</div>
                      <div className="text-[10px] font-mono text-slate-500 uppercase">{pos.chainId}</div>
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[9px] text-slate-500">ENTRY</div>
                    <div className="font-mono text-xs text-slate-300">${pos.entry_price}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[9px] text-slate-500">CURRENT</div>
                    <div className="font-mono text-xs text-white">${pos.current_price}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[9px] text-slate-500">SIZE</div>
                    <div className="font-mono text-xs text-slate-300">${pos.amount_usd}</div>
                  </div>
                  <div className="ml-auto text-right">
                    <div className="text-[9px] text-slate-500">PnL</div>
                    <div className={`font-mono text-lg font-bold ${pos.pnl_pct >= 0 ? "neon-text-green" : "neon-text-magenta"}`}>
                      {pos.pnl_pct >= 0 ? "+" : ""}{pos.pnl_pct.toFixed(1)}%
                    </div>
                  </div>
                </motion.div>
              ))}
              {positions.length === 0 && (
                <div className="text-center text-slate-600 font-mono text-sm py-16">
                  No active positions. Start the swarm to begin hunting.
                </div>
              )}
            </div>
          )}

          {tab === "trades" && (
            <div className="space-y-2">
              {trades.map((trade, i) => (
                <motion.div
                  key={trade.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className="cyber-panel px-4 py-3 flex items-center gap-6"
                  data-testid={`trade-row-${i}`}
                >
                  <div className="min-w-[80px]">
                    <div className="font-mono text-sm font-bold text-white">{trade.symbol}</div>
                    <div className="text-[10px] font-mono text-slate-500">{trade.chainId}</div>
                  </div>
                  <div className={`px-2 py-0.5 text-[10px] font-mono border ${
                    trade.side === "BUY" ? "border-green-500/30 text-green-400" : "border-red-500/30 text-red-400"
                  }`}>
                    {trade.side}
                  </div>
                  <div className="text-center">
                    <div className="text-[9px] text-slate-500">PRICE</div>
                    <div className="font-mono text-xs text-slate-300">${trade.price}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[9px] text-slate-500">SIZE</div>
                    <div className="font-mono text-xs text-slate-300">${trade.amount_usd}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[9px] text-slate-500">SCORE</div>
                    <div className="font-mono text-xs text-cyan-400">{trade.score}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[9px] text-slate-500">VERDICT</div>
                    <div className={`font-mono text-xs ${
                      trade.security?.verdict === "SAFE" ? "text-green-400" :
                      trade.security?.verdict === "DANGER" ? "text-red-400" : "text-yellow-400"
                    }`}>
                      {trade.security?.verdict || "N/A"}
                    </div>
                  </div>
                  <div className="ml-auto">
                    <span className={`px-2 py-0.5 text-[10px] font-mono border ${
                      trade.status === "SIMULATED" ? "border-yellow-500/30 text-yellow-400" : "border-green-500/30 text-green-400"
                    }`}>
                      {trade.status}
                    </span>
                  </div>
                </motion.div>
              ))}
              {trades.length === 0 && (
                <div className="text-center text-slate-600 font-mono text-sm py-16">
                  No trades yet. Activate the swarm to start.
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
