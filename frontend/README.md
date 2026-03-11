# APEX-SWARM Frontend

Next.js dashboard for the APEX-SWARM God-Mode crypto trading command center.

## Run

```bash
npm run dev    # http://localhost:3000
```

Requires the backend to be running at `http://localhost:8000` (set via `NEXT_PUBLIC_BACKEND_URL` in `.env.local`).

## Routes

| Route | Description |
|---|---|
| `/` | OVERWATCH — main cyberpunk trading HUD |
| `/positions` | Active positions table |
| `/settings` | Agent configuration |
| `/office` | TinyOffice (proxied to port 4001 — TinyClaw agent office visualization) |

## Key Components

- `NeuralFeed` — Real-time agent activity log via WebSocket
- `AlphaRadar` — Token momentum radar (DexScreener data)
- `CrossChainMatrix` — Cross-chain liquidity routing map
- `PnLChart` — Equity curve using lightweight-charts
- `PositionsGrid` — Open positions with live PnL
- `SwarmControl` — Start/stop the swarm + agent status cards
