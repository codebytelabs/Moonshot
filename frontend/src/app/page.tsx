"use client";
import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { apiFetch } from "@/lib/api";
import { useSwarmSocket, WsMessage } from "@/lib/useWebSocket";
import Sidebar from "@/components/Sidebar";
import NeuralFeed from "@/components/NeuralFeed";
import AlphaRadar from "@/components/AlphaRadar";
import PnLChart from "@/components/PnLChart";
import CrossChainMatrix from "@/components/CrossChainMatrix";
import PositionsGrid from "@/components/PositionsGrid";
import SwarmControl from "@/components/SwarmControl";
import StatsBar from "@/components/StatsBar";

interface AgentLog {
  agent: string;
  status: string;
  message: string;
  timestamp: string;
}

export default function Dashboard() {
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [alphaHits, setAlphaHits] = useState<unknown[]>([]);
  const [portfolio, setPortfolio] = useState<Array<{ value: number; timestamp: string }>>([]);
  const [positions, setPositions] = useState<unknown[]>([]);
  const [swarmActive, setSwarmActive] = useState(false);
  const { messages, connected } = useSwarmSocket();

  // Initial data fetch
  useEffect(() => {
    const load = async () => {
      try {
        const [dash, logsData, hitsData, portData, posData] = await Promise.all([
          apiFetch("/api/dashboard"),
          apiFetch("/api/agent-logs?limit=200"),
          apiFetch("/api/alpha-hits?limit=50"),
          apiFetch("/api/portfolio"),
          apiFetch("/api/positions"),
        ]);
        setDashboard(dash);
        setLogs(logsData.reverse());
        setAlphaHits(hitsData);
        setPortfolio(portData);
        setPositions(posData);
        setSwarmActive(dash.swarm_active);
      } catch (e) {
        console.error("Load error:", e);
      }
    };
    load();
  }, []);

  // Process WebSocket messages
  useEffect(() => {
    if (messages.length === 0) return;
    const latest = messages[messages.length - 1];
    if (!latest) return;

    switch (latest.type) {
      case "agent_log":
        setLogs((prev) => [...prev, latest.data as unknown as AgentLog].slice(-500));
        break;
      case "radar_hit":
        setAlphaHits((prev) => [latest.data, ...prev].slice(0, 50));
        break;
      case "trade_executed":
        setPositions((prev) => [latest.data, ...prev]);
        break;
    }
  }, [messages]);

  const toggleSwarm = async () => {
    try {
      if (swarmActive) {
        await apiFetch("/api/swarm/stop", { method: "POST" });
        setSwarmActive(false);
      } else {
        await apiFetch("/api/swarm/start", { method: "POST" });
        setSwarmActive(true);
      }
    } catch (e) {
      console.error("Swarm toggle error:", e);
    }
  };

  return (
    <div className="flex h-screen bg-[#050505]" data-testid="dashboard-root">
      <Sidebar />

      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Header bar */}
        <header className="h-12 border-b border-cyan-900/20 bg-[#0A0F0D]/80 backdrop-blur-sm flex items-center px-4 gap-4 shrink-0" data-testid="header">
          <h1
            className="font-[Orbitron] text-sm font-black tracking-[0.3em] uppercase neon-text-cyan"
            style={{ fontFamily: "Orbitron" }}
          >
            APEX-SWARM
          </h1>
          <span className="text-[10px] font-mono text-slate-600">v1.0 // GOD-MODE</span>
          <div className="ml-auto flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-[10px] font-mono ${connected ? "text-green-400" : "text-red-400"}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
              {connected ? "WS CONNECTED" : "WS DISCONNECTED"}
            </div>
            <span className="text-[10px] font-mono text-slate-600">
              {new Date().toLocaleTimeString("en-US", { hour12: false })}
            </span>
          </div>
        </header>

        {/* Stats bar */}
        <div className="px-3 py-2 shrink-0">
          <StatsBar
            data={
              dashboard
                ? {
                    portfolio_value: (dashboard.portfolio_value as number) || 10000,
                    active_positions: (dashboard.active_positions as number) || 0,
                    total_trades: (dashboard.total_trades as number) || 0,
                    total_alpha_hits: (dashboard.total_alpha_hits as number) || 0,
                    swarm_active: swarmActive,
                    wallets: (dashboard.wallets as { evm: string; sol: string }) || { evm: "", sol: "" },
                  }
                : null
            }
          />
        </div>

        {/* Main grid */}
        <div className="flex-1 min-h-0 px-3 pb-3 grid grid-cols-12 grid-rows-2 gap-2">
          {/* Neural Feed - left column */}
          <motion.div
            className="col-span-3 row-span-2"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
          >
            <NeuralFeed logs={logs} />
          </motion.div>

          {/* Alpha Radar - top middle */}
          <motion.div
            className="col-span-4 row-span-1"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <AlphaRadar hits={alphaHits as never[]} />
          </motion.div>

          {/* Cross-Chain Matrix - top right */}
          <motion.div
            className="col-span-3 row-span-1"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
          >
            <CrossChainMatrix routes={[]} />
          </motion.div>

          {/* Swarm Control - top far right */}
          <motion.div
            className="col-span-2 row-span-1"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <SwarmControl swarmActive={swarmActive} onToggle={toggleSwarm} agentLogs={logs} />
          </motion.div>

          {/* PnL Chart - bottom middle */}
          <motion.div
            className="col-span-5 row-span-1"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.25 }}
          >
            <PnLChart data={portfolio} />
          </motion.div>

          {/* Positions Grid - bottom right */}
          <motion.div
            className="col-span-4 row-span-1"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            <PositionsGrid positions={positions as never[]} />
          </motion.div>
        </div>
      </main>
    </div>
  );
}
