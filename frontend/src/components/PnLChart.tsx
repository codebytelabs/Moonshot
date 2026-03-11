"use client";
import { useEffect, useRef } from "react";
import { createChart, ColorType, LineStyle, AreaSeries } from "lightweight-charts";

interface DataPoint {
  value: number;
  timestamp: string;
}

export default function PnLChart({ data }: { data: DataPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    // Cleanup previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#475569",
        fontFamily: "JetBrains Mono",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(0, 243, 255, 0.04)" },
        horzLines: { color: "rgba(0, 243, 255, 0.04)" },
      },
      crosshair: {
        vertLine: { color: "rgba(0, 243, 255, 0.3)", style: LineStyle.Dashed },
        horzLine: { color: "rgba(0, 243, 255, 0.3)", style: LineStyle.Dashed },
      },
      rightPriceScale: {
        borderColor: "rgba(0, 243, 255, 0.1)",
      },
      timeScale: {
        borderColor: "rgba(0, 243, 255, 0.1)",
        timeVisible: true,
      },
    });

    chartRef.current = chart;

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: "#00F3FF",
      topColor: "rgba(0, 243, 255, 0.3)",
      bottomColor: "rgba(0, 243, 255, 0.02)",
      lineWidth: 2,
    });

    const formatted = data
      .map((d) => ({
        time: Math.floor(new Date(d.timestamp).getTime() / 1000) as import("lightweight-charts").UTCTimestamp,
        value: d.value,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));

    areaSeries.setData(formatted);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    const observer = new ResizeObserver(handleResize);
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data]);

  const latest = data.length > 0 ? data[data.length - 1].value : 0;
  const first = data.length > 0 ? data[0].value : 0;
  const pnl = first > 0 ? ((latest - first) / first) * 100 : 0;

  return (
    <div className="cyber-panel h-full flex flex-col" data-testid="pnl-chart">
      <div className="px-3 py-2 border-b border-cyan-900/30 flex items-center gap-2 shrink-0">
        <div className="w-2 h-2 rounded-full bg-[#39FF14] animate-pulse" />
        <h3 className="font-[Orbitron] text-xs tracking-[0.2em] uppercase neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
          Equity Curve
        </h3>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-[10px] font-mono text-slate-500">NAV</span>
          <span className="font-mono text-sm font-bold neon-text-green">${latest.toLocaleString()}</span>
          <span className={`font-mono text-xs ${pnl >= 0 ? "neon-text-green" : "neon-text-magenta"}`}>
            {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
          </span>
        </div>
      </div>
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  );
}
