"use client";
import { useEffect, useRef, useMemo } from "react";
import { motion } from "framer-motion";

interface AlphaHit {
  id: string;
  chainId: string;
  baseToken: { symbol: string; name: string; address: string };
  priceUsd: string;
  score: number;
  volume: { m5: number; h1: number; h24: number };
  liquidity_usd: number;
  priceChange: { m5: number; h1: number };
  source: string;
}

const CHAIN_COLORS: Record<string, string> = {
  ethereum: "#627EEA",
  solana: "#9945FF",
  base: "#0052FF",
  bsc: "#F0B90B",
  polygon: "#8247E5",
  arbitrum: "#12AAFF",
  optimism: "#FF0420",
  avalanche: "#E84142",
};

export default function AlphaRadar({ hits }: { hits: AlphaHit[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Draw radar sweep animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width = canvas.offsetWidth * 2;
    const h = canvas.height = canvas.offsetHeight * 2;
    ctx.scale(2, 2);
    const cw = w / 4;
    const ch = h / 4;
    const maxR = Math.min(cw, ch) * 0.85;

    let angle = 0;
    let animId: number;

    const draw = () => {
      ctx.clearRect(0, 0, w / 2, h / 2);

      // Grid circles
      for (let i = 1; i <= 4; i++) {
        ctx.beginPath();
        ctx.arc(cw, ch, (maxR / 4) * i, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0, 243, 255, ${0.05 + i * 0.02})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      // Cross lines
      ctx.strokeStyle = "rgba(0, 243, 255, 0.08)";
      ctx.beginPath();
      ctx.moveTo(cw - maxR, ch);
      ctx.lineTo(cw + maxR, ch);
      ctx.moveTo(cw, ch - maxR);
      ctx.lineTo(cw, ch + maxR);
      ctx.stroke();

      // Sweep
      const gradient = ctx.createConicGradient(angle, cw, ch);
      gradient.addColorStop(0, "rgba(0, 243, 255, 0.15)");
      gradient.addColorStop(0.1, "rgba(0, 243, 255, 0)");
      gradient.addColorStop(1, "rgba(0, 243, 255, 0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(cw, ch, maxR, 0, Math.PI * 2);
      ctx.fill();

      // Sweep line
      ctx.beginPath();
      ctx.moveTo(cw, ch);
      ctx.lineTo(cw + Math.cos(angle) * maxR, ch + Math.sin(angle) * maxR);
      ctx.strokeStyle = "rgba(0, 243, 255, 0.6)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Token blips
      hits.slice(0, 20).forEach((hit, i) => {
        const a = (i / 20) * Math.PI * 2 + 0.5;
        const dist = maxR * (1 - hit.score / 120);
        const x = cw + Math.cos(a) * dist;
        const y = ch + Math.sin(a) * dist;
        const r = Math.max(3, Math.min(8, hit.score / 10));
        const color = CHAIN_COLORS[hit.chainId] || "#00F3FF";

        // Glow
        const grd = ctx.createRadialGradient(x, y, 0, x, y, r * 3);
        grd.addColorStop(0, color + "60");
        grd.addColorStop(1, "transparent");
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(x, y, r * 3, 0, Math.PI * 2);
        ctx.fill();

        // Dot
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = "#fff";
        ctx.font = "9px JetBrains Mono";
        ctx.fillText(hit.baseToken?.symbol || "?", x + r + 3, y + 3);
      });

      // Center dot
      ctx.fillStyle = "#00F3FF";
      ctx.beginPath();
      ctx.arc(cw, ch, 3, 0, Math.PI * 2);
      ctx.fill();

      angle += 0.02;
      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animId);
  }, [hits]);

  return (
    <div className="cyber-panel h-full flex flex-col" data-testid="alpha-radar">
      <div className="px-3 py-2 border-b border-cyan-900/30 flex items-center gap-2 shrink-0">
        <div className="w-2 h-2 rounded-full bg-[#00F3FF] animate-pulse" />
        <h3 className="font-[Orbitron] text-xs tracking-[0.2em] uppercase neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
          Alpha Radar
        </h3>
        <span className="ml-auto text-[10px] font-mono text-slate-600">{hits.length} targets</span>
      </div>
      <div className="flex-1 relative">
        <canvas ref={canvasRef} className="w-full h-full" style={{ imageRendering: "auto" }} />
        {/* Chain legend */}
        <div className="absolute bottom-2 left-2 flex flex-wrap gap-x-3 gap-y-1">
          {Object.entries(CHAIN_COLORS).slice(0, 6).map(([chain, color]) => (
            <div key={chain} className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
              <span className="text-[9px] font-mono text-slate-500 uppercase">{chain.slice(0, 3)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
