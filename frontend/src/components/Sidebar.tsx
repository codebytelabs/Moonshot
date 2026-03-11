"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, List, Settings, Radio, ChevronLeft, ChevronRight, Network } from "lucide-react";

const NAV = [
  { href: "/", label: "OVERWATCH", icon: LayoutDashboard },
  { href: "/swarm", label: "TINYCLAW", icon: Network },
  { href: "/positions", label: "POSITIONS", icon: List },
  { href: "/settings", label: "CONFIG", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`h-full bg-[#0A0F0D] border-r border-cyan-900/20 flex flex-col transition-all duration-300 ${collapsed ? "w-14" : "w-48"}`}
      data-testid="sidebar"
    >
      {/* Logo */}
      <div className="px-3 py-4 border-b border-cyan-900/20 flex items-center gap-2">
        <Radio size={18} className="text-cyan-400 shrink-0 animate-pulse" />
        {!collapsed && (
          <span className="font-[Orbitron] text-sm font-black tracking-widest neon-text-cyan" style={{ fontFamily: "Orbitron" }}>
            APEX
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 space-y-0.5 px-2">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className={`flex items-center gap-2.5 px-2.5 py-2 text-xs font-mono tracking-wider transition-all ${
                active
                  ? "bg-cyan-500/10 text-cyan-400 border-l-2 border-cyan-400"
                  : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.02] border-l-2 border-transparent"
              }`}
            >
              <item.icon size={14} className="shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="p-3 border-t border-cyan-900/20 text-slate-600 hover:text-cyan-400 transition-colors flex justify-center"
        data-testid="sidebar-collapse-btn"
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  );
}
