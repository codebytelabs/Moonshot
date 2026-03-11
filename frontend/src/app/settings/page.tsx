"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { apiFetch } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { Cpu, Wallet, Globe, Sliders, Shield } from "lucide-react";

interface SettingsData {
  primary_model: string;
  fallback_model: string;
  evm_wallet: string;
  sol_wallet: string;
  scan_interval: number;
  max_position_size: number;
  chains: string[];
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData | null>(null);

  useEffect(() => {
    apiFetch("/api/settings").then(setSettings).catch(console.error);
  }, []);

  if (!settings) {
    return (
      <div className="flex h-screen bg-[#050505]">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <div className="font-mono text-sm text-slate-600 animate-pulse">Loading configuration...</div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#050505]" data-testid="settings-page">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-12 border-b border-cyan-900/20 bg-[#0A0F0D]/80 backdrop-blur-sm flex items-center px-4 gap-4 shrink-0">
          <h1 className="font-[Orbitron] text-sm font-black tracking-[0.3em] uppercase neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
            CONFIGURATION
          </h1>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* AI Models */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="cyber-panel p-4">
            <div className="flex items-center gap-2 mb-4">
              <Cpu size={16} className="text-cyan-400" />
              <h2 className="font-[Orbitron] text-xs tracking-wider uppercase text-cyan-400" style={{ fontFamily: "Orbitron" }}>
                AI Models
              </h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-mono text-slate-500 uppercase block mb-1">Primary Model</label>
                <div className="bg-black/40 border border-cyan-900/20 px-3 py-2 font-mono text-xs text-cyan-400" data-testid="primary-model">
                  {settings.primary_model}
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono text-slate-500 uppercase block mb-1">Fallback Model</label>
                <div className="bg-black/40 border border-cyan-900/20 px-3 py-2 font-mono text-xs text-yellow-400" data-testid="fallback-model">
                  {settings.fallback_model}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Wallets */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="cyber-panel p-4">
            <div className="flex items-center gap-2 mb-4">
              <Wallet size={16} className="text-cyan-400" />
              <h2 className="font-[Orbitron] text-xs tracking-wider uppercase text-cyan-400" style={{ fontFamily: "Orbitron" }}>
                Wallets
              </h2>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-mono text-slate-500 uppercase block mb-1">EVM (ETH/BASE/BSC/POLY)</label>
                <div className="bg-black/40 border border-cyan-900/20 px-3 py-2 font-mono text-[11px] text-slate-300 break-all" data-testid="evm-wallet">
                  {settings.evm_wallet}
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono text-slate-500 uppercase block mb-1">Solana</label>
                <div className="bg-black/40 border border-cyan-900/20 px-3 py-2 font-mono text-[11px] text-slate-300 break-all" data-testid="sol-wallet">
                  {settings.sol_wallet}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Execution Config */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="cyber-panel p-4">
            <div className="flex items-center gap-2 mb-4">
              <Sliders size={16} className="text-cyan-400" />
              <h2 className="font-[Orbitron] text-xs tracking-wider uppercase text-cyan-400" style={{ fontFamily: "Orbitron" }}>
                Execution Parameters
              </h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-mono text-slate-500 uppercase block mb-1">Scan Interval</label>
                <div className="bg-black/40 border border-cyan-900/20 px-3 py-2 font-mono text-xs text-green-400" data-testid="scan-interval">
                  {settings.scan_interval}s
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono text-slate-500 uppercase block mb-1">Max Position Size</label>
                <div className="bg-black/40 border border-cyan-900/20 px-3 py-2 font-mono text-xs text-green-400" data-testid="max-position">
                  ${settings.max_position_size}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Chains */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="cyber-panel p-4">
            <div className="flex items-center gap-2 mb-4">
              <Globe size={16} className="text-cyan-400" />
              <h2 className="font-[Orbitron] text-xs tracking-wider uppercase text-cyan-400" style={{ fontFamily: "Orbitron" }}>
                Target Chains
              </h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {settings.chains.map((chain) => (
                <span
                  key={chain}
                  className="px-3 py-1 border border-cyan-900/30 text-[10px] font-mono text-cyan-400 uppercase bg-cyan-400/5"
                  data-testid={`chain-${chain}`}
                >
                  {chain}
                </span>
              ))}
            </div>
          </motion.div>

          {/* Execution Stack */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="cyber-panel p-4">
            <div className="flex items-center gap-2 mb-4">
              <Shield size={16} className="text-cyan-400" />
              <h2 className="font-[Orbitron] text-xs tracking-wider uppercase text-cyan-400" style={{ fontFamily: "Orbitron" }}>
                Execution Stack
              </h2>
            </div>
            <div className="space-y-2">
              {[
                { label: "Cross-Chain Routing", value: "LI.FI MCP", status: "Phase 2" },
                { label: "Gasless Execution", value: "Pimlico (EIP-7702)", status: "Phase 2" },
                { label: "MEV Protection", value: "Flashbots Protect", status: "Phase 2" },
                { label: "Contract Auditing", value: "OpenRouter AI", status: "Active" },
                { label: "Market Scanner", value: "DexScreener API", status: "Active" },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3 px-3 py-2 bg-black/20">
                  <span className="text-[10px] font-mono text-slate-500 w-40">{item.label}</span>
                  <span className="text-[11px] font-mono text-slate-300">{item.value}</span>
                  <span className={`ml-auto text-[9px] font-mono px-2 py-0.5 border ${
                    item.status === "Active"
                      ? "border-green-500/30 text-green-400"
                      : "border-yellow-500/30 text-yellow-400"
                  }`}>
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  );
}
