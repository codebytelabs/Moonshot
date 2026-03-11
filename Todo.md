# APEX-SWARM — Vision, Status & Roadmap

## 🎯 Vision: God-Mode Autonomous Crypto Trading

A self-organizing swarm of 11 AI agents that continuously scans markets, audits contracts, calculates probability, manages risk, and executes cross-chain trades — all without human input.

---

## ✅ What Is Actually Working Right Now

### Infrastructure (All Real — Verified March 2026)
| Component | Status | Notes |
|---|---|---|
| FastAPI backend (port 8000) | ✅ Live | All 20+ endpoints tested |
| Next.js OVERWATCH dashboard (port 3000) | ✅ Live | Real-time data flowing |
| MongoDB | ✅ Live | alpha_hits, trades, positions, logs stored |
| TinyClaw daemon (port 3777) | ✅ Live | 11 agents registered |
| TinyOffice (port 4001, embedded at /office) | ✅ Live | All 11 agents visible |
| Telegram → @bigbrother | ✅ Connected | Bot token configured |

### Agent Pipeline (What Each Agent Actually Does)
| Agent | Real? | What It Does |
|---|---|---|
| @alpha_scanner | ✅ **REAL** | Scans DexScreener live boosted+profile tokens, 50 candidates per cycle |
| @contract_sniper | ✅ **REAL** | Heuristic security audit + OpenRouter Qwen3.5-397B LLM audit |
| @execution_core | ⚠️ **PARTIAL** | Calls real LI.FI REST API for quotes, gets real transactionRequest, but does NOT sign/broadcast |
| @quant_mutator | ✅ **REAL** | Evaluates hit_rate/avg_score, mutates scanner_config in-memory + MongoDB |
| @tinyclaw | ✅ **REAL** | OpenRouter LLM orchestrates each cycle, generates directives |
| @bigbrother | ✅ **REAL** | TinyClaw agent, responds via Telegram |
| Others (watcher, analyzer, etc.) | ✅ **DEFINED** | Full AGENTS.md in TinyOffice |

### LI.FI Integration Status (Audit Results)
- ✅ REST API integrated and calling live (`https://li.quest/v1`)
- ✅ EVM token addresses correctly sourced from `pair.baseToken.address`
- ✅ Flashbots RPC configured: `https://rpc.flashbots.net`
- ⚠️ **LI.FI returns "No quotes" (code 1002) for micro-cap/obscure tokens** — expected, not a bug
- ❌ No Pimlico key → no EIP-7702 UserOp signing → no actual broadcast

---

## ❌ What Is NOT Real Right Now

| Feature | Status | Why |
|---|---|---|
| **Actual trade execution** | ❌ Paper only | No `PIMLICO_API_KEY` → UserOp can't be signed |
| **Broadcast via Flashbots** | ❌ Not wired | Configured but not connected to signing flow |
| **LI.FI quotes for micro-caps** | ❌ Often fail | Error 1002: token too obscure for DEX aggregators |
| **On-chain bytecode reads** | ❌ Heuristics only | No web3 bytecode fetcher yet |
| **Real P&L** | ❌ Simulated | All positions are paper trades |

---

## ⚠️ Strategy Assessment

### The Flow
1. Scan DexScreener boosted tokens (high 5-min volume, buy/sell imbalance, new pairs under 24h)
2. Heuristic + LLM security gate — block DANGER tokens
3. Route via LI.FI (best DEX price) for EVM tokens
4. $50 USDC position size per trade
5. Quant mutator adjusts thresholds based on live hit_rate

### Honest Risks
- 🔴 **No exit logic** — system enters but never exits. A rug at -100% is kept forever
- 🔴 **Micro-caps too small for LI.FI** — the tokens we scan are too tiny for DEX aggregators
- 🔴 **No backtesting** — no data on whether this is profitable
- 🟡 **Solana memecoins dominate** — highest risk category even with audits
- 🟡 **Position sizing uncapped** — 10 trades × $50 = $500 per cycle with no portfolio cap check

### Verdict: **Promising infrastructure, incomplete for real money**
Do NOT use real funds until: (1) exit logic is added, (2) position risk caps are enforced, (3) 30 days of paper simulation is analyzed.

---

## 🗺️ Roadmap

### P0 — Real Execution (1-2 days)
- [ ] Add `PIMLICO_API_KEY` from pimlico.io
- [ ] Integrate `permissionless.js` to sign EIP-7702 UserOp from LI.FI `transactionRequest`
- [ ] Submit via Flashbots Protect RPC
- [ ] Filter scanner to only tokens with > $100k pool (for LI.FI routability)

### P1 — Exit Management (2-3 days)
- [ ] Trailing stop (close at -20% from peak)
- [ ] Time-based exit (close after 24h if no 2x)
- [ ] @position_mgr polls positions and triggers exit

### P2 — Better Token Quality (1 week)
- [ ] On-chain bytecode reads via web3.py
- [ ] Jupiter DEX integration for Solana
- [ ] Birdeye API for better Solana data

### P3 — Strategy Improvement (2-4 weeks)
- [ ] 30-day paper trade backtest
- [ ] @bayesian probabilistic position sizing
- [ ] @risk_mgr hard circuit breaker (halt at >15% drawdown)

### P4 — Production (1 month+)
- [ ] Docker deployment + auto-restart
- [ ] Multi-wallet (separate paper/real)
- [ ] Telegram alerts on every trade

---

## 🚀 Running The System

```bash
bash /Users/vishnuvardhanmedara/Moonshot/start.sh
```

### Environment Variables
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=apex_swarm
OPENROUTER_API_KEY=sk-or-...        # Required for LLM agents
EVM_WALLET_ADDRESS=0x...
SOL_WALLET_ADDRESS=...

# To unlock real execution:
PIMLICO_API_KEY=pim_...             # Get from pimlico.io
LIFI_API_KEY=...                    # Optional, increases rate limits
```

### Key URLs
| URL | What |
|---|---|
| http://localhost:3000 | OVERWATCH Dashboard |
| http://localhost:3000/office | TinyOffice (11 agents) |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/api/execution/status | LI.FI + Flashbots config |
| http://localhost:8000/api/lifi/quote | Test real LI.FI quote |
| http://localhost:8000/api/scanner/config | Live scanner params |
