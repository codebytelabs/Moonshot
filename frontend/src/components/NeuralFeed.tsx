"use client";
import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

interface AgentLog {
  agent: string;
  status: string;
  message: string;
  timestamp: string;
}

const AGENT_COLORS: Record<string, string> = {
  alpha_scanner: "#00F3FF",
  contract_sniper: "#FF003C",
  execution_core: "#39FF14",
  quant_mutator: "#FFD700",
  system: "#94A3B8",
};

const STATUS_ICONS: Record<string, string> = {
  SCANNING: ">>",
  DETECTED: "!!",
  LOCKED: "**",
  DECOMPILING: "[]",
  CLEAR: "OK",
  BLOCKED: "XX",
  CAUTION: "??",
  ROUTING: "->",
  EXECUTED: "$$",
  ANALYZING: "~~",
  MUTATED: "++",
  CYCLE: "==",
  COMPLETE: "//",
  BOOT: "::",
  READY: "--",
  ERROR: "!!",
  HALTED: "##",
  IDLE: "..",
};

export default function NeuralFeed({ logs }: { logs: AgentLog[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="cyber-panel h-full flex flex-col" data-testid="neural-feed">
      <div className="px-3 py-2 border-b border-cyan-900/30 flex items-center gap-2 shrink-0">
        <div className="w-2 h-2 rounded-full bg-[#39FF14] animate-pulse" />
        <h3
          className="font-[Orbitron] text-xs tracking-[0.2em] uppercase neon-text-cyan"
          style={{ fontFamily: "Orbitron" }}
        >
          Neural Feed
        </h3>
        <span className="ml-auto text-[10px] font-mono text-slate-600">{logs.length} entries</span>
      </div>

      <div ref={containerRef} className="flex-1 overflow-y-auto p-2 space-y-0.5" style={{ scrollBehavior: "smooth" }}>
        {logs.map((log, i) => {
          const color = AGENT_COLORS[log.agent] || "#94A3B8";
          const icon = STATUS_ICONS[log.status] || ">>";
          return (
            <motion.div
              key={`${log.timestamp}-${i}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.15 }}
              className="font-mono text-[11px] leading-relaxed flex gap-1 hover:bg-white/[0.02] px-1 rounded-sm"
              data-testid={`log-entry-${i}`}
            >
              <span className="text-slate-600 shrink-0 w-[60px]">
                {new Date(log.timestamp).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
              <span className="shrink-0" style={{ color }}>[{icon}]</span>
              <span className="shrink-0 font-bold" style={{ color }}>
                @{log.agent}
              </span>
              <span className="text-slate-400 break-all">{log.message}</span>
            </motion.div>
          );
        })}
        {logs.length === 0 && (
          <div className="text-center text-slate-600 font-mono text-xs py-8">
            Awaiting swarm initialization...
          </div>
        )}
      </div>
    </div>
  );
}
