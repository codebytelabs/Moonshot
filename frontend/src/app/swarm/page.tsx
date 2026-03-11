"use client";
import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiFetch } from "@/lib/api";
import { useSwarmSocket } from "@/lib/useWebSocket";
import Sidebar from "@/components/Sidebar";
import {
  Activity, Shield, Zap, Brain, Network,
  ChevronDown, ChevronRight, RefreshCw, Power, PowerOff,
  AlertTriangle, CheckCircle, Clock, Target, BarChart2, Layers
} from "lucide-react";

interface AgentLog {
  agent: string;
  status: string;
  message: string;
  timestamp: string;
}

interface AgentData {
  role: string;
  description: string;
  color: string;
  status: "active" | "idle" | "error";
  cycles?: number;
  decisions?: number;
  hits_found?: number;
  audits_done?: number;
  threats_blocked?: number;
  total_blocked?: number;
  trades_executed?: number;
  trades_skipped?: number;
  total_trades?: number;
  mutations?: number;
  total_mutations?: number;
  total_hits?: number;
  last_action?: string;
  recent_logs?: AgentLog[];
}

interface AgentsResponse {
  swarm_active: boolean;
  cycle_count: number;
  agents: Record<string, AgentData>;
}

const AGENT_ICONS: Record<string, React.ReactNode> = {
  tinyclaw: <Network size={18} />,
  alpha_scanner: <Activity size={18} />,
  contract_sniper: <Shield size={18} />,
  execution_core: <Zap size={18} />,
  quant_mutator: <Brain size={18} />,
};

const STATUS_ICONS: Record<string, string> = {
  SCANNING: ">>", DETECTED: "!!", LOCKED: "**", DECOMPILING: "[]",
  CLEAR: "OK", BLOCKED: "XX", CAUTION: "??", ROUTING: "->",
  EXECUTED: "$$", ANALYZING: "~~", MUTATED: "++", CYCLE: "==",
  COMPLETE: "//", BOOT: "::", READY: "--", ERROR: "!!", HALTED: "##",
  IDLE: "..", DIRECTIVE: "=>", ABORTED: "||",
};

function AgentCard({ name, data, expanded, onToggle }: {
  name: string;
  data: AgentData;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isOrchestrator = name === "tinyclaw";
  const color = data.color || "#00F3FF";
  const isActive = data.status === "active";

  const stats = [];
  if (data.cycles !== undefined) stats.push({ label: "Cycles", value: data.cycles });
  if (data.hits_found !== undefined) stats.push({ label: "Hits Found", value: data.hits_found });
  if (data.total_hits !== undefined && data.hits_found === undefined) stats.push({ label: "Total Hits", value: data.total_hits });
  if (data.audits_done !== undefined) stats.push({ label: "Audited", value: data.audits_done });
  if (data.threats_blocked !== undefined) stats.push({ label: "Blocked", value: data.threats_blocked });
  if (data.total_blocked !== undefined && data.threats_blocked === undefined) stats.push({ label: "Total Blocked", value: data.total_blocked });
  if (data.trades_executed !== undefined) stats.push({ label: "Executed", value: data.trades_executed });
  if (data.trades_skipped !== undefined) stats.push({ label: "Skipped", value: data.trades_skipped });
  if (data.total_trades !== undefined && data.trades_executed === undefined) stats.push({ label: "Total Trades", value: data.total_trades });
  if (data.mutations !== undefined) stats.push({ label: "Mutations", value: data.mutations });
  if (data.decisions !== undefined) stats.push({ label: "Decisions", value: data.decisions });

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`cyber-panel overflow-hidden transition-all ${isOrchestrator ? "border-cyan-400/30" : ""}`}
      style={isActive ? { boxShadow: `0 0 18px ${color}22` } : {}}
      data-testid={`agent-card-${name}`}
    >
      {/* Card Header */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        {/* Status dot */}
        <div className="relative shrink-0">
          <div
            className={`w-2 h-2 rounded-full ${isActive ? "animate-pulse" : ""}`}
            style={{ background: isActive ? color : "#334155" }}
          />
          {isActive && (
            <div
              className="absolute inset-0 w-2 h-2 rounded-full animate-ping opacity-40"
              style={{ background: color }}
            />
          )}
        </div>

        {/* Icon */}
        <div className="shrink-0" style={{ color }}>
          {AGENT_ICONS[name]}
        </div>

        {/* Name & role */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="font-mono text-sm font-bold tracking-wider"
              style={{ color, fontFamily: "Orbitron" }}
            >
              @{name}
            </span>
            {isOrchestrator && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 border border-cyan-400/30 text-cyan-400 uppercase tracking-wider">
                ORCHESTRATOR
              </span>
            )}
            <span
              className={`ml-auto text-[9px] font-mono px-2 py-0.5 border ${
                isActive
                  ? "border-green-500/30 text-green-400 bg-green-400/5"
                  : "border-slate-700 text-slate-500"
              }`}
            >
              {isActive ? "ACTIVE" : "IDLE"}
            </span>
          </div>
          <div className="text-[10px] font-mono text-slate-500 mt-0.5">{data.role}</div>
        </div>

        {expanded ? (
          <ChevronDown size={12} className="text-slate-600 shrink-0" />
        ) : (
          <ChevronRight size={12} className="text-slate-600 shrink-0" />
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3 border-t border-white/[0.04]">
              {/* Description */}
              <p className="text-[11px] font-mono text-slate-400 pt-3 leading-relaxed">
                {data.description}
              </p>

              {/* Last action */}
              {data.last_action && (
                <div className="bg-black/30 border border-white/[0.04] px-3 py-2">
                  <div className="text-[9px] font-mono text-slate-600 uppercase mb-1">Last Action</div>
                  <div className="text-[11px] font-mono" style={{ color }}>
                    {data.last_action}
                  </div>
                </div>
              )}

              {/* Stats grid */}
              {stats.length > 0 && (
                <div className="grid grid-cols-3 gap-2">
                  {stats.map((s) => (
                    <div key={s.label} className="bg-black/20 border border-white/[0.03] px-2 py-1.5 text-center">
                      <div className="font-mono font-bold text-sm" style={{ color }}>
                        {s.value}
                      </div>
                      <div className="text-[9px] font-mono text-slate-600 uppercase mt-0.5">
                        {s.label}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Recent logs */}
              {data.recent_logs && data.recent_logs.length > 0 && (
                <div>
                  <div className="text-[9px] font-mono text-slate-600 uppercase mb-2">Recent Activity</div>
                  <div className="space-y-1">
                    {data.recent_logs.map((log, i) => {
                      const icon = STATUS_ICONS[log.status] || ">>";
                      return (
                        <div key={i} className="flex gap-2 font-mono text-[10px] leading-relaxed">
                          <span className="text-slate-700 shrink-0 w-[55px]">
                            {new Date(log.timestamp).toLocaleTimeString("en-US", {
                              hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
                            })}
                          </span>
                          <span className="shrink-0 w-6" style={{ color }}>[{icon}]</span>
                          <span className="text-slate-400 break-all">{log.message}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function SwarmPage() {
  const [agentsData, setAgentsData] = useState<AgentsResponse | null>(null);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set(["tinyclaw"]));
  const [loading, setLoading] = useState(true);
  const [swarmActive, setSwarmActive] = useState(false);
  const [toggling, setToggling] = useState(false);
  const { messages } = useSwarmSocket();

  const fetchAgents = useCallback(async () => {
    try {
      const data = await apiFetch("/api/agents/status");
      setAgentsData(data);
      setSwarmActive(data.swarm_active);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
    const interval = setInterval(fetchAgents, 5000);
    return () => clearInterval(interval);
  }, [fetchAgents]);

  // Handle live metric updates from WebSocket
  useEffect(() => {
    if (messages.length === 0) return;
    const latest = messages[messages.length - 1];
    if (latest?.type === "agent_metrics" && agentsData) {
      const updatedMetrics = latest.data as Record<string, AgentData>;
      setAgentsData((prev) => {
        if (!prev) return prev;
        const newAgents = { ...prev.agents };
        for (const [k, v] of Object.entries(updatedMetrics)) {
          if (newAgents[k]) {
            newAgents[k] = { ...newAgents[k], status: v.status, last_action: v.last_action };
          }
        }
        return { ...prev, agents: newAgents };
      });
    }
    if (latest?.type === "agent_log") {
      const log = latest.data as unknown as AgentLog;
      setAgentsData((prev) => {
        if (!prev) return prev;
        const agent = prev.agents[log.agent];
        if (!agent) return prev;
        const updated = {
          ...agent,
          recent_logs: [...(agent.recent_logs || []).slice(-4), log],
        };
        return { ...prev, agents: { ...prev.agents, [log.agent]: updated } };
      });
    }
  }, [messages]);

  const toggleSwarm = async () => {
    setToggling(true);
    try {
      if (swarmActive) {
        await apiFetch("/api/swarm/stop", { method: "POST" });
        setSwarmActive(false);
      } else {
        await apiFetch("/api/swarm/start", { method: "POST" });
        setSwarmActive(true);
      }
      setTimeout(fetchAgents, 1000);
    } finally {
      setToggling(false);
    }
  };

  const toggleExpand = (name: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const agentOrder = ["tinyclaw", "alpha_scanner", "contract_sniper", "execution_core", "quant_mutator"];

  return (
    <div className="flex h-screen bg-[#050505]" data-testid="swarm-page">
      <Sidebar />

      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Header */}
        <header className="h-12 border-b border-cyan-900/20 bg-[#0A0F0D]/80 backdrop-blur-sm flex items-center px-4 gap-4 shrink-0">
          <Network size={14} className="text-cyan-400" />
          <h1
            className="font-mono text-sm font-black tracking-[0.3em] uppercase neon-text-cyan"
            style={{ fontFamily: "Orbitron" }}
          >
            TINYCLAW // AGENT TEAM
          </h1>
          <span className="text-[10px] font-mono text-slate-600">
            {agentsData ? `${agentsData.cycle_count} cycles run` : "loading..."}
          </span>
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={fetchAgents}
              className="text-slate-600 hover:text-cyan-400 transition-colors"
              title="Refresh"
              data-testid="refresh-agents-btn"
            >
              <RefreshCw size={12} />
            </button>
            <button
              onClick={toggleSwarm}
              disabled={toggling}
              data-testid="swarm-toggle-btn"
              className={`flex items-center gap-1.5 px-3 py-1 text-[10px] font-mono tracking-wider border transition-all ${
                swarmActive
                  ? "bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20"
                  : "bg-green-500/10 border-green-500/30 text-green-400 hover:bg-green-500/20"
              }`}
              style={{ fontFamily: "Orbitron" }}
            >
              {swarmActive ? <PowerOff size={10} /> : <Power size={10} />}
              {swarmActive ? "STOP SWARM" : "LAUNCH SWARM"}
            </button>
          </div>
        </header>

        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center h-full text-slate-600 font-mono text-sm animate-pulse">
              Initializing TinyClaw...
            </div>
          ) : (
            <div className="max-w-5xl mx-auto space-y-4">
              {/* Top swarm status banner */}
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="cyber-panel px-4 py-3 flex items-center gap-4"
                data-testid="swarm-status-banner"
              >
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2.5 h-2.5 rounded-full ${swarmActive ? "bg-green-400 animate-pulse" : "bg-red-400"}`}
                  />
                  <span className="font-mono text-sm font-bold" style={{ fontFamily: "Orbitron" }}>
                    {swarmActive ? (
                      <span className="neon-text-green">SWARM ONLINE</span>
                    ) : (
                      <span className="neon-text-magenta">SWARM OFFLINE</span>
                    )}
                  </span>
                </div>
                <div className="h-4 w-px bg-cyan-900/30" />
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
                  <Layers size={10} />
                  <span>{agentOrder.length} agents deployed</span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
                  <Target size={10} />
                  <span>{agentsData?.agents?.alpha_scanner?.total_hits ?? 0} total alpha hits</span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
                  <BarChart2 size={10} />
                  <span>{agentsData?.agents?.execution_core?.total_trades ?? 0} trades executed</span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
                  <AlertTriangle size={10} />
                  <span>{agentsData?.agents?.contract_sniper?.total_blocked ?? 0} threats blocked</span>
                </div>
                <div className="ml-auto flex items-center gap-1.5 text-[10px] font-mono">
                  <Clock size={10} className="text-slate-600" />
                  <span className="text-slate-600">Cycle #{agentsData?.cycle_count ?? 0}</span>
                </div>
              </motion.div>

              {/* TinyClaw topology diagram */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.1 }}
                className="cyber-panel px-4 py-3"
              >
                <div className="text-[9px] font-mono text-slate-600 uppercase tracking-wider mb-3">
                  Agent Topology
                </div>
                <div className="flex items-center justify-center gap-0 overflow-x-auto py-2">
                  {/* TinyClaw center */}
                  <div className="flex flex-col items-center shrink-0">
                    <div
                      className="w-14 h-14 border-2 flex items-center justify-center relative"
                      style={{ borderColor: "#00F3FF", boxShadow: "0 0 20px #00F3FF33" }}
                    >
                      <Network size={22} className="text-cyan-400" />
                      {swarmActive && (
                        <div className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-green-400 animate-pulse" />
                      )}
                    </div>
                    <div className="text-[9px] font-mono text-cyan-400 mt-1.5 tracking-widest">TINYCLAW</div>
                    <div className="text-[8px] font-mono text-slate-600">ORCHESTRATOR</div>
                  </div>

                  {/* Connectors + sub-agents */}
                  {[
                    { id: "alpha_scanner", label: "ALPHA", icon: <Activity size={16} />, color: "#00F3FF" },
                    { id: "contract_sniper", label: "SNIPER", icon: <Shield size={16} />, color: "#FF003C" },
                    { id: "execution_core", label: "EXEC", icon: <Zap size={16} />, color: "#39FF14" },
                    { id: "quant_mutator", label: "QUANT", icon: <Brain size={16} />, color: "#FFD700" },
                  ].map((agent) => {
                    const isActive = agentsData?.agents?.[agent.id]?.status === "active";
                    return (
                      <div key={agent.id} className="flex items-center shrink-0">
                        {/* Line */}
                        <div className="flex flex-col items-center">
                          <div
                            className={`w-8 h-px transition-colors ${isActive ? "bg-cyan-400/60" : "bg-cyan-900/30"}`}
                          />
                          {isActive && (
                            <motion.div
                              animate={{ x: [0, 28] }}
                              transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
                              className="w-1.5 h-1.5 rounded-full -mt-0.5"
                              style={{ background: agent.color, marginLeft: "-1px" }}
                            />
                          )}
                        </div>
                        {/* Node */}
                        <button
                          onClick={() => toggleExpand(agent.id)}
                          className="flex flex-col items-center group"
                        >
                          <div
                            className="w-10 h-10 border flex items-center justify-center transition-all group-hover:scale-110"
                            style={{
                              borderColor: isActive ? agent.color : "#1e293b",
                              boxShadow: isActive ? `0 0 12px ${agent.color}33` : "none",
                              color: isActive ? agent.color : "#475569",
                            }}
                          >
                            {agent.icon}
                          </div>
                          <div
                            className="text-[8px] font-mono mt-1.5 tracking-widest"
                            style={{ color: isActive ? agent.color : "#475569" }}
                          >
                            {agent.label}
                          </div>
                          <div className={`text-[7px] font-mono ${isActive ? "text-green-400" : "text-slate-600"}`}>
                            {isActive ? "ACTIVE" : "IDLE"}
                          </div>
                        </button>
                      </div>
                    );
                  })}
                </div>
              </motion.div>

              {/* Agent cards */}
              <div className="space-y-2">
                {agentOrder.map((name, i) => {
                  const data = agentsData?.agents?.[name];
                  if (!data) return null;
                  return (
                    <motion.div
                      key={name}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.05 * i }}
                    >
                      <AgentCard
                        name={name}
                        data={data}
                        expanded={expandedAgents.has(name)}
                        onToggle={() => toggleExpand(name)}
                      />
                    </motion.div>
                  );
                })}
              </div>

              {/* Bottom note */}
              <div className="text-center text-[10px] font-mono text-slate-700 py-2">
                TinyClaw v1.0 // APEX-SWARM Orchestration Layer //
                {swarmActive ? " Swarm is active and scanning" : " Launch swarm to begin scanning"}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
