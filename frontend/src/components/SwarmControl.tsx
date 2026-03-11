"use client";
import { motion } from "framer-motion";
import { Activity, Cpu, Shield, Zap, Brain, Power, PowerOff } from "lucide-react";

interface AgentStatus {
  name: string;
  icon: React.ReactNode;
  status: "active" | "idle" | "error";
  lastAction: string;
  color: string;
}

const AGENTS: AgentStatus[] = [
  { name: "@alpha_scanner", icon: <Activity size={14} />, status: "idle", lastAction: "Scanning DexScreener...", color: "#00F3FF" },
  { name: "@contract_sniper", icon: <Shield size={14} />, status: "idle", lastAction: "Awaiting targets...", color: "#FF003C" },
  { name: "@execution_core", icon: <Zap size={14} />, status: "idle", lastAction: "Routing engine ready", color: "#39FF14" },
  { name: "@quant_mutator", icon: <Brain size={14} />, status: "idle", lastAction: "Strategy nominal", color: "#FFD700" },
];

interface Props {
  swarmActive: boolean;
  onToggle: () => void;
  agentLogs: Array<{ agent: string; status: string; message: string; timestamp: string }>;
}

export default function SwarmControl({ swarmActive, onToggle, agentLogs }: Props) {
  const agents = AGENTS.map((a) => {
    const latest = agentLogs.filter((l) => l.agent === a.name.replace("@", "")).slice(-1)[0];
    return {
      ...a,
      status: swarmActive ? ("active" as const) : ("idle" as const),
      lastAction: latest?.message || a.lastAction,
    };
  });

  return (
    <div className="cyber-panel h-full flex flex-col" data-testid="swarm-control">
      <div className="px-3 py-2 border-b border-cyan-900/30 flex items-center gap-2 shrink-0">
        <Cpu size={12} className="text-cyan-400" />
        <h3 className="font-[Orbitron] text-xs tracking-[0.2em] uppercase neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
          Swarm Control
        </h3>
      </div>

      <div className="p-3 space-y-2 flex-1">
        {/* Power toggle */}
        <button
          onClick={onToggle}
          data-testid="swarm-toggle-btn"
          className={`w-full py-2.5 font-[Orbitron] text-xs tracking-widest uppercase flex items-center justify-center gap-2 border transition-all ${
            swarmActive
              ? "bg-[#39FF14]/10 border-[#39FF14]/40 text-[#39FF14] hover:bg-[#39FF14]/20 animate-pulse-glow"
              : "bg-[#FF003C]/10 border-[#FF003C]/40 text-[#FF003C] hover:bg-[#FF003C]/20"
          }`}
          style={{ fontFamily: "Orbitron" }}
        >
          {swarmActive ? <Power size={14} /> : <PowerOff size={14} />}
          {swarmActive ? "SWARM ACTIVE" : "ACTIVATE SWARM"}
        </button>

        {/* Agent status */}
        <div className="space-y-1.5 mt-3">
          {agents.map((agent) => (
            <motion.div
              key={agent.name}
              className="flex items-center gap-2 px-2 py-1.5 bg-white/[0.02] border border-transparent hover:border-cyan-900/30 transition-colors"
              data-testid={`agent-status-${agent.name}`}
            >
              <div
                className={`w-1.5 h-1.5 rounded-full ${agent.status === "active" ? "animate-pulse" : ""}`}
                style={{ background: agent.status === "active" ? agent.color : "#475569" }}
              />
              <span className="font-mono text-[10px] font-bold shrink-0" style={{ color: agent.color }}>
                {agent.name}
              </span>
              <span className="font-mono text-[9px] text-slate-500 truncate ml-auto max-w-[100px]">
                {agent.lastAction.slice(0, 30)}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
