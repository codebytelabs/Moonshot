import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'MOONSHOT — Trading Bot Dashboard',
  description: 'Autonomous AI multi-agent crypto trading bot command center',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
