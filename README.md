<div align="center">

```
 █████╗ ██████╗ ███████╗██╗  ██╗      ███████╗██╗    ██╗ █████╗ ██████╗ ███╗   ███╗
██╔══██╗██╔══██╗██╔════╝╚██╗██╔╝      ██╔════╝██║    ██║██╔══██╗██╔══██╗████╗ ████║
███████║██████╔╝█████╗   ╚███╔╝ █████╗███████╗██║ █╗ ██║███████║██████╔╝██╔████╔██║
██╔══██║██╔═══╝ ██╔══╝   ██╔██╗ ╚════╝╚════██║██║███╗██║██╔══██║██╔══██╗██║╚██╔╝██║
██║  ██║██║     ███████╗██╔╝ ██╗       ███████║╚███╔███╔╝██║  ██║██║  ██║██║ ╚═╝ ██║
╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝       ╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
```

**Unconstrained Personal God-Mode Autonomous Crypto Trading Matrix**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![TinyClaw](https://img.shields.io/badge/TinyClaw-Multi--Agent-6366F1?style=flat-square)](https://github.com/TinyAGI/tinyclaw)
[![Chains](https://img.shields.io/badge/Chains-60+-F7931A?style=flat-square&logo=ethereum&logoColor=white)]()
[![License](https://img.shields.io/badge/License-Private-red?style=flat-square)]()

*Built for maximum alpha extraction. No KYC. No retail limits. No mercy.*

</div>

---

## What is APEX-SWARM?

APEX-SWARM is a private, personal autonomous crypto trading system built for a single operator — you. It deploys a swarm of 11 AI agents that scan 60+ blockchains, audit contracts for rug risk, and execute cross-chain trades gaslessly in sub-seconds, while you watch it all unfold in a cyberpunk God-Mode dashboard.

This is not a trading bot. It's a full autonomous trading organisation, managed by AI.

> **Architecture in one line:**
> *TinyClaw agents scan DexScreener → audit contracts → route capital via LI.FI MCP → execute gaslessly via Pimlico EIP-7702 → stealth broadcast via Flashbots Protect*

---

## Core Capabilities

| Capability | Technology | What It Does |
|---|---|---|
| 🔍 **Deep Market Vision** | DexScreener API | Scans micro-cap pairs every 60s — sub-minute liquidity pools across 60+ chains |
| 🛡️ **Dark Execution** | Flashbots Protect RPC | Routes all transactions through a private mempool — zero MEV sandwich attacks |
| ⛽ **Gasless Speed** | Pimlico + EIP-7702 | Agents never fund gas wallets — delegated execution via Account Abstraction |
| 🌉 **Zero-Friction Liquidity** | LI.FI MCP | Bridges and swaps USDC cross-chain in a single tool call — 27+ bridges, 31+ DEXes |
| 🧠 **AI Consensus** | TinyClaw Multi-Agent | 11 agents run in parallel with real LLM reasoning — not scripted logic |
| 🔄 **Self-Mutating Strategy** | Quant Mutator | Rewrites its own scanner parameters when win rate decays |
| 🖥️ **God-Mode Dashboard** | Next.js + WebSocket | Cyberpunk real-time command centre — Neural Feed, Alpha Radar, PnL charts |
| 📱 **Telegram Control** | TinyClaw + Telegram | Talk to `@bigbrother` on Telegram — live system status, trade reports, commands |

---

## The Agent Swarm

All 11 agents are real autonomous LLM agents managed by TinyClaw. They communicate with each other, call live APIs, and make decisions without human input.

```
                           ┌──────────────────────┐
                           │   @bigbrother         │  ← Supervisor
                           │   (GLM-5)             │     Talk to on Telegram
                           └──────────┬───────────┘
                ┌───────────┬─────────┼─────────┬───────────┐
                ▼           ▼         ▼         ▼           ▼
         ┌────────────┐  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
         │@alpha_scan │  │@watcher│ │@analyz │ │@context│ │@quant_mut│
         │DexScreener │  │CEX scan│ │Multi-TF│ │Narrativ│ │Mutates   │
         │60+ chains  │  │USDT prs│ │TA + ATR│ │enrichmt│ │strategy  │
         └─────┬──────┘  └───┬────┘ └───┬────┘ └───┬────┘ └──────────┘
               ▼             └──────────┤           │
         ┌────────────┐          ┌──────▼───────────▼──┐
         │@contract_  │          │@bayesian             │
         │sniper      │          │Posterior score       │
         │Honeypot    │          │enter/skip/reject     │
         │audit       │          └──────────┬───────────┘
         └─────┬──────┘                     ▼
               └──────────────────► ┌──────────────┐
                                    │@execution_core│
                                    │LI.FI MCP      │
                                    │→ Pimlico      │
                                    │→ Flashbots    │
                                    └───────┬───────┘
                              ┌────────────┼─────────────┐
                              ▼            ▼             ▼
                        ┌──────────┐ ┌──────────┐ ┌──────────┐
                        │@position │ │@risk_mgr │ │  CHAINS  │
                        │_mgr      │ │Drawdown  │ │ETH/SOL/  │
                        │Tiered    │ │guard     │ │BASE/ARB  │
                        │exits     │ │          │ │+ 57 more │
                        └──────────┘ └──────────┘ └──────────┘
```

### Agent Roster

| Agent | Model | Responsibility |
|---|---|---|
| `@bigbrother` | GLM-5 | Master supervisor — routes commands, aggregates status, Telegram gateway |
| `@alpha_scanner` | Qwen3.5-397B | Polls DexScreener for 5m volume spikes, buyer momentum, new pairs |
| `@contract_sniper` | Qwen3.5-397B | Audits token contracts — honeypot detection, rug patterns, tax abuse |
| `@execution_core` | Qwen3.5-397B | LI.FI cross-chain routing → Pimlico gasless → Flashbots broadcast |
| `@quant_mutator` | Qwen3.5-397B | Evaluates win rate daily, rewrites scanner thresholds if strategy decays |
| `@watcher` | Qwen3.5-397B | Scans CEX USDT pairs in scalper/surfer/sniper mode |
| `@analyzer` | Qwen3.5-397B | Multi-timeframe TA — breakout/momentum/pullback/mean-reversion classification |
| `@context` | Qwen3.5-397B | Semantic enrichment — narratives, listings, airdrop catalysts (Sniper mode) |
| `@bayesian` | Qwen3.5-397B | Probabilistic posterior score → ENTER / SKIP / REJECT |
| `@position_mgr` | Qwen3.5-397B | Tiered exits (25% at 2R, 25% at 5R, 50% runner), trailing stops |
| `@risk_mgr` | Qwen3.5-397B | Hard limits: 20% max drawdown, 8 max positions, daily loss guard |

---

## Dashboard — OVERWATCH God-Mode Interface

The **OVERWATCH** interface is a browser-based cyberpunk command centre streaming live swarm data in real time.

| Panel | What It Shows |
|---|---|
| **Neural Feed** | Scrolling matrix-style log — watch agents think in real time |
| **Alpha Radar** | DexScreener anomaly scatter plot — bubbles pulse as tokens gain traction |
| **Cross-Chain Matrix** | Animated LI.FI routing visualisation — capital moving across chains |
| **PnL Command Centre** | Equity curve + trade history (Lightweight Charts) |
| **Swarm Control** | Start/stop, mode switch, live cycle metrics |
| **`/office`** | TinyOffice — pixel-art animated office with all 11 agents at their desks |

---

## Tech Stack

### Backend
- **FastAPI** — async REST API + WebSocket streaming
- **Motor** — async MongoDB driver
- **HTTPX** — async HTTP client for DexScreener + OpenRouter
- **OpenRouter** — LLM gateway (Qwen3.5-397B primary, Kimi-K2.5 fallback)
- **MongoDB** — trade history, alpha hits, agent logs
- **Redis** — pub/sub for real-time event streaming

### Frontend
- **Next.js 15** — app router, React 19
- **TailwindCSS** — cyberpunk styling
- **Framer Motion** — animations for radar bubbles, routing matrix
- **Lightweight Charts** — TradingView-grade equity curve
- **Socket.io** — sub-second WebSocket streaming from agents to UI

### Agent Orchestration
- **TinyClaw** — multi-agent framework with isolated workspaces, Telegram/Discord integration
- **TinyOffice** — pixel-art animated office visualising all agents live

### Execution Layer *(P0 target)*
- **LI.FI MCP** — cross-chain quote + bridge/swap in a single tool call
- **Pimlico** — EIP-7702 gasless UserOps (no gas wallet management)
- **Flashbots Protect** — private mempool, zero sandwich attacks

---

## Quickstart

### Prerequisites

```bash
# Required
Python 3.11+
Node.js 18+
MongoDB (running locally)
Redis (running locally)
TinyClaw CLI (npm i -g tinyclaw)
```

### 1. Clone & Configure

```bash
git clone https://github.com/codebytelabs/Moonshot
cd Moonshot
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)
```

### 2. Install Dependencies

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# TinyOffice
cd tinyclaw/tinyoffice && npm install && cd ../..
```

### 3. Launch Everything

```bash
bash start.sh
```

That's it. One command starts:
- FastAPI backend on `:8000`
- Next.js dashboard on `:3000`
- TinyClaw daemon (Telegram connected)
- TinyOffice on `:4001` (embedded at `/office`)

### 4. Open the Dashboard

| URL | What You See |
|---|---|
| `http://localhost:3000` | APEX-SWARM God-Mode cyberpunk dashboard |
| `http://localhost:3000/office` | All 11 agents at their desks, animated live |
| `http://localhost:8000/docs` | FastAPI interactive API documentation |

### 5. Start the Swarm

```bash
# Via UI: click "INITIATE SWARM" on the dashboard
# Or via API:
curl -X POST http://localhost:8000/api/swarm/start

# Or message @bigbrother on Telegram:
# "Start scanning"
```

---

## Environment Variables

```env
# Database
MONGO_URL=mongodb://localhost:27017
DB_NAME=apex_swarm

# LLM Gateway
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_PRIMARY_MODEL=qwen/qwen3.5-397b-a17b
OPENROUTER_FALLBACK_MODEL=moonshotai/kimi-k2.5

# Wallets (no withdrawal permissions required)
PVT_KEY_WALLET=0x...
EVM_WALLET_ADDRESS=0x...
SOL_WALLET_ADDRESS=...

# Execution (P0 — add when ready)
PIMLICO_API_KEY=pim_...
LIFI_API_KEY=...
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System health + uptime |
| `GET` | `/api/agents/status` | All agent cycle metrics |
| `GET` | `/api/alpha-hits` | Latest DexScreener discoveries |
| `GET` | `/api/trades` | Complete trade history |
| `GET` | `/api/positions` | Open positions |
| `GET` | `/api/dashboard` | Portfolio overview + chain distribution |
| `GET` | `/api/dex/trending` | Boosted/trending tokens |
| `GET` | `/api/dex/token/{chain}/{address}` | Deep pair data for a token |
| `POST` | `/api/swarm/start` | Start automated scan loop |
| `POST` | `/api/swarm/stop` | Stop scan loop |
| `WS` | `/ws` | Real-time event stream → dashboard |

Interactive docs at `http://localhost:8000/docs`

---

## Roadmap

```
P0 — Real Execution Engine                     🔴 In Progress
├── LI.FI MCP cross-chain routing (mcp.li.quest)
├── Pimlico EIP-7702 gasless UserOps
└── Flashbots Protect RPC broadcast

P1 — Real Contract Auditing                    🟡 Planned
├── On-chain bytecode reads (ethers.js)
├── Solana Rugcheck API integration
└── Honeypot pattern recognition

P2 — Self-Mutating Strategy                    🟡 Planned
├── @quant_mutator hot-reloads MongoDB scanner config
├── LLM-generated threshold mutations
└── Win rate → parameter feedback loop

P3 — CoinGecko MCP + Macro Regime              🟡 Planned
├── BTC market regime detection
└── Auto-switch: acceleration→scalper / bear→sniper

P4 — Real Position Management                  🟡 Planned
├── Tiered exits (25% at 2R, 25% at 5R, 50% runner)
├── Trailing stops (25-35% below peak)
└── Pyramiding on winners
```

---

## Project Structure

```
Moonshot/
├── backend/
│   └── server.py              # FastAPI app — APIs, WebSocket, agent scan loop
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx           # OVERWATCH God-Mode dashboard
│   │   ├── office/page.tsx    # TinyOffice iframe embed
│   │   ├── swarm/             # Swarm control panel
│   │   └── positions/         # Position tracker
│   └── next.config.ts
├── tinyclaw/
│   └── tinyoffice/            # TinyOffice pixel-art animated office
├── .agents/                   # TinyClaw agent workspaces
│   ├── bigbrother/AGENTS.md
│   ├── alpha_scanner/AGENTS.md
│   ├── contract_sniper/AGENTS.md
│   ├── execution_core/AGENTS.md
│   ├── quant_mutator/AGENTS.md
│   ├── watcher/AGENTS.md
│   ├── analyzer/AGENTS.md
│   ├── context/AGENTS.md
│   ├── bayesian/AGENTS.md
│   ├── position_mgr/AGENTS.md
│   └── risk_mgr/AGENTS.md
├── memory/                    # System context + PRD
├── requirements.txt
├── start.sh                   # One-command full-stack launcher
├── Todo.md                    # Live roadmap + current status
└── .env                       # Your credentials (never commit this)
```

---

## References

- [LI.FI MCP Server](https://docs.li.fi/mcp-server/overview) — Cross-chain swap tool calls
- [Pimlico EIP-7702 Guide](https://docs.pimlico.io/guides/eip7702) — Gasless Account Abstraction
- [Flashbots Protect](https://docs.flashbots.net/flashbots-protect/overview) — MEV protection
- [DexScreener API](https://docs.dexscreener.com) — Live micro-cap pair data
- [TinyClaw](https://github.com/TinyAGI/tinyclaw) — Multi-agent framework

---

<div align="center">

**Built for one operator. Designed for maximum alpha. No compromises.**

*Private system — not for public deployment.*

</div>
