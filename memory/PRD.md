# APEX-SWARM // Product Requirements Document

**Last Updated:** 2026-03-11
**Status:** Phase 1 Complete + TinyClaw Orchestrator Live

---

## Original Problem Statement
Build a personal, highly aggressive multi-agent crypto trading system named "APEX-SWARM" in "degen mode." The system prioritizes speed and alpha extraction. Features a cyberpunk "God-Mode" browser command center with real-time agent monitoring.

---

## Architecture

```
/app/
├── backend/
│   ├── .env                          # MONGO_URL, DB_NAME, OPENROUTER keys, wallets
│   ├── requirements.txt
│   └── server.py                     # FastAPI + all agents + WebSocket
└── frontend/
    ├── .env                          # NEXT_PUBLIC_BACKEND_URL
    ├── src/app/
    │   ├── page.tsx                  # Main dashboard (OVERWATCH)
    │   ├── swarm/page.tsx            # TinyClaw Agent Team UI (NEW)
    │   ├── positions/page.tsx
    │   └── settings/page.tsx
    └── src/components/
        ├── Sidebar.tsx               # Nav: OVERWATCH | TINYCLAW | POSITIONS | CONFIG
        ├── NeuralFeed.tsx
        ├── AlphaRadar.tsx
        ├── CrossChainMatrix.tsx
        ├── PnLChart.tsx
        ├── PositionsGrid.tsx
        ├── SwarmControl.tsx
        └── StatsBar.tsx
```

---

## Agent Architecture

### TinyClaw (Master Orchestrator)
- Manages cycle flow and agent coordination
- Issues directives based on cycle results
- Tracks: cycles, decisions, last_action

### @alpha_scanner
- Scans DexScreener profiles + boosted tokens
- Scores tokens by momentum (volume, txns, liquidity, price change)
- Tracks: hits_found per cycle

### @contract_sniper
- Heuristic + AI (OpenRouter LLM) analysis
- Honeypot, rug-pull, liquidity checks
- Tracks: audits_done, threats_blocked

### @execution_core
- Routes trades (currently SIMULATED)
- Planned: LI.FI + Pimlico EIP-7702
- Tracks: trades_executed, trades_skipped

### @quant_mutator
- Evaluates win rate every 5 cycles
- Suggests strategy parameter changes
- Tracks: mutations

---

## DB Schema (MongoDB: apex_swarm)
- `trades`: { symbol, chainId, side, price, amount_usd, status, route, timestamp }
- `portfolio`: { value, timestamp }
- `positions`: { symbol, chainId, entry_price, current_price, amount_usd, pnl_pct, status }
- `agent_logs`: { agent, status, message, timestamp }
- `alpha_hits`: { chainId, tokenAddress, pairAddress, score, volume, liquidity_usd, ... }
- `strategy_mutations`: { timestamp, total_trades, analysis }

---

## Key Endpoints
- `WS /api/ws` — Real-time agent events (agent_log, radar_hit, trade_executed, agent_metrics)
- `GET /api/agents/status` — Full agent team status + metrics + recent logs
- `POST /api/swarm/start` / `POST /api/swarm/stop`
- `GET /api/dashboard` — Portfolio, positions, trades summary
- `GET /api/agent-logs` — Historical agent logs

---

## Integrations
- **OpenRouter** (working): qwen/qwen3.5-397b-a17b + moonshotai/kimi-k2.5 fallback
- **DexScreener** (working): Live token scanning, no key required
- **(Planned)** LI.FI: Cross-chain bridging
- **(Planned)** Pimlico + EIP-7702: Gasless execution
- **(Planned)** Flashbots Protect: MEV protection

---

## What's Been Implemented

### 2026-03-11 (Session 2)
- Added TinyClaw as master orchestrator agent in backend
- Added per-agent metrics tracking (cycles, hits, audits, trades, mutations)
- Added `/api/agents/status` endpoint with rich per-agent data
- Built `/swarm` page: TinyClaw Command Center with topology diagram + agent cards
- Updated sidebar: OVERWATCH | TINYCLAW | POSITIONS | CONFIG
- Fixed OpenRouter key (new key working for completions)
- TinyClaw orchestrates all 4 sub-agents with live directives

### 2026-01-XX (Session 1)
- Full cyberpunk "God-Mode" dashboard
- Multi-agent swarm backend (4 agents + system)
- WebSocket streaming + DexScreener integration
- MongoDB persistence
- Neural Feed, Alpha Radar, Cross-Chain Matrix, PnL Chart, Positions

---

## P0 Backlog (Next Priority)

### Phase 2: Real Execution Engine
- Replace `@execution_core` simulated trades with LI.FI `get_quote` + execute
- Pimlico SDK for EIP-7702 gasless UserOps
- Connect wallet (private key from .env) to sign transactions

### Phase 3: MEV Protection
- Route all transactions via Flashbots Protect RPC
- Update execution_core to use private mempool

### @quant_mutator LLM-Powered Strategy
- Use OpenRouter to actually modify scanner parameters based on win rate
- Store evolved parameters in MongoDB settings collection

## P1 Backlog

### Wallet Authentication
- Connect crypto wallet to protect dashboard access
- Sign-in with Ethereum (SIWE) or Solana wallet

### PnL Tracking
- Track actual entry/exit prices from execution
- Real-time PnL updates via WebSocket

## P2 Backlog
- Position management: manual close, stop-loss, take-profit
- Multi-wallet support
- Alert system (Telegram/Discord webhook on new alpha hits)
- Historical performance analytics
