import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "APEX-SWARM | God-Mode Trading Matrix",
  description: "Unconstrained Multi-Agent DEX Trading Command Center",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-[#050505] text-slate-200 overflow-hidden h-screen">
        <div className="scanline-overlay" />
        {children}
      </body>
    </html>
  );
}
