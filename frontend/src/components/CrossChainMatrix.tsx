"use client";
import { useEffect, useRef } from "react";

interface ChainNode {
  id: string;
  label: string;
  color: string;
  x: number;
  y: number;
}

const CHAINS: ChainNode[] = [
  { id: "ethereum", label: "ETH", color: "#627EEA", x: 0.5, y: 0.15 },
  { id: "base", label: "BASE", color: "#0052FF", x: 0.25, y: 0.35 },
  { id: "arbitrum", label: "ARB", color: "#12AAFF", x: 0.75, y: 0.35 },
  { id: "solana", label: "SOL", color: "#9945FF", x: 0.15, y: 0.65 },
  { id: "bsc", label: "BSC", color: "#F0B90B", x: 0.5, y: 0.55 },
  { id: "polygon", label: "POLY", color: "#8247E5", x: 0.85, y: 0.65 },
  { id: "optimism", label: "OP", color: "#FF0420", x: 0.35, y: 0.85 },
  { id: "avalanche", label: "AVAX", color: "#E84142", x: 0.65, y: 0.85 },
];

interface Route {
  from: string;
  to: string;
  progress: number;
}

export default function CrossChainMatrix({ routes }: { routes: Route[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = (canvas.width = canvas.offsetWidth * 2);
    const h = (canvas.height = canvas.offsetHeight * 2);
    ctx.scale(2, 2);
    const cw = w / 4;
    const ch = h / 4;

    let tick = 0;
    let animId: number;

    const draw = () => {
      ctx.clearRect(0, 0, cw * 2, ch * 2);

      // Draw connections (subtle grid)
      CHAINS.forEach((a) => {
        CHAINS.forEach((b) => {
          if (a.id >= b.id) return;
          ctx.beginPath();
          ctx.moveTo(a.x * cw * 2, a.y * ch * 2);
          ctx.lineTo(b.x * cw * 2, b.y * ch * 2);
          ctx.strokeStyle = "rgba(0, 243, 255, 0.04)";
          ctx.lineWidth = 0.5;
          ctx.stroke();
        });
      });

      // Draw active routes with animated packets
      const activeRoutes = routes.length > 0 ? routes : [
        { from: "ethereum", to: "base", progress: (tick * 0.01) % 1 },
        { from: "base", to: "solana", progress: ((tick * 0.008) + 0.3) % 1 },
        { from: "arbitrum", to: "bsc", progress: ((tick * 0.012) + 0.6) % 1 },
      ];

      activeRoutes.forEach((route) => {
        const from = CHAINS.find((c) => c.id === route.from);
        const to = CHAINS.find((c) => c.id === route.to);
        if (!from || !to) return;

        const fx = from.x * cw * 2, fy = from.y * ch * 2;
        const tx = to.x * cw * 2, ty = to.y * ch * 2;

        // Active line
        ctx.beginPath();
        ctx.moveTo(fx, fy);
        ctx.lineTo(tx, ty);
        ctx.strokeStyle = "rgba(0, 243, 255, 0.2)";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Animated packet
        const p = ((tick * 0.01) + (route.progress || 0)) % 1;
        const px = fx + (tx - fx) * p;
        const py = fy + (ty - fy) * p;

        const grd = ctx.createRadialGradient(px, py, 0, px, py, 12);
        grd.addColorStop(0, "rgba(0, 243, 255, 0.8)");
        grd.addColorStop(1, "transparent");
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(px, py, 12, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#00F3FF";
        ctx.beginPath();
        ctx.arc(px, py, 2, 0, Math.PI * 2);
        ctx.fill();
      });

      // Draw chain nodes
      CHAINS.forEach((chain) => {
        const x = chain.x * cw * 2;
        const y = chain.y * ch * 2;

        // Outer glow
        const grd = ctx.createRadialGradient(x, y, 0, x, y, 20);
        grd.addColorStop(0, chain.color + "40");
        grd.addColorStop(1, "transparent");
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(x, y, 20, 0, Math.PI * 2);
        ctx.fill();

        // Node ring
        ctx.beginPath();
        ctx.arc(x, y, 10, 0, Math.PI * 2);
        ctx.strokeStyle = chain.color;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Node fill
        ctx.fillStyle = chain.color + "30";
        ctx.fill();

        // Inner dot
        ctx.fillStyle = chain.color;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = "#fff";
        ctx.font = "bold 9px JetBrains Mono";
        ctx.textAlign = "center";
        ctx.fillText(chain.label, x, y + 22);
      });

      tick++;
      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animId);
  }, [routes]);

  return (
    <div className="cyber-panel h-full flex flex-col" data-testid="cross-chain-matrix">
      <div className="px-3 py-2 border-b border-cyan-900/30 flex items-center gap-2 shrink-0">
        <div className="w-2 h-2 rounded-full bg-[#00F3FF] animate-pulse" />
        <h3 className="font-[Orbitron] text-xs tracking-[0.2em] uppercase neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
          Cross-Chain Matrix
        </h3>
        <span className="ml-auto text-[10px] font-mono text-slate-600">LI.FI Routes</span>
      </div>
      <div className="flex-1 relative">
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>
    </div>
  );
}
