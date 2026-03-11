# APEX-SWARM: God-Mode Trading Matrix - PRD

## Original Problem Statement
Build a multi-agent crypto trading system (APEX-SWARM) with cyberpunk God-Mode UI. 4 AI agents (@alpha_scanner, @contract_sniper, @execution_core, @quant_mutator) autonomously scan DexScreener for micro-cap tokens, audit contracts, and execute trades. Cyberpunk Overwatch interface with Neural Feed, Alpha Radar, Cross-Chain Matrix, PnL Command Center.

## Architecture
- **Backend**: FastAPI (Python) + MongoDB + WebSocket on port 8001
- **Frontend**: Next.js (TypeScript) + TailwindCSS v4 + Framer Motion + TradingView Lightweight Charts on port 3000
- **Data Source**: DexScreener free API (token profiles, boosted tokens, pair search, token pairs)
- **AI Models**: OpenRouter (qwen/qwen3.5-397b-a17b primary, moonshotai/kimi-k2.5 fallback) + heuristic fallback
- **Chains**: Ethereum, Solana, Base, BSC, Polygon, Arbitrum, Optimism, Avalanche

## User Personas
- Single power user (personal trading terminal)
- Maximum risk tolerance, degen mode

## Core Requirements
1. Multi-agent swarm scanning DexScreener every 60s
2. Contract safety analysis (heuristic + LLM)
3. Simulated trade execution with scoring
4. Real-time WebSocket streaming to UI
5. Cyberpunk God-Mode aesthetic
6. Cross-chain visualization
7. Portfolio tracking with equity curve

## What's Been Implemented (March 11, 2026)

### Backend
- [x] FastAPI server with 12+ REST endpoints
- [x] WebSocket real-time broadcasting with timeout protection
- [x] @alpha_scanner: Polls DexScreener token-profiles + boosted tokens, scores by volume/buys/liquidity/FDV
- [x] @contract_sniper: Heuristic + LLM-enhanced contract safety analysis (honeypot, liquidity, risk scoring)
- [x] @execution_core: Simulated trade execution with route info
- [x] @quant_mutator: Strategy performance evaluation
- [x] DexScreener proxy endpoints (search, trending, token data)
- [x] MongoDB persistence (agent_logs, alpha_hits, trades, positions, portfolio, strategy_mutations)
- [x] Seed data for positions (PEPE, WIF, BRETT) and portfolio equity curve

### Frontend
- [x] Cyberpunk God-Mode dashboard with bento grid layout
- [x] Neural Feed: Live scrolling agent logs with color-coded agents and timestamps
- [x] Alpha Radar: Canvas-based radar sweep with chain-colored token blips
- [x] Cross-Chain Matrix: Animated network graph with packet routing
- [x] PnL Command Center: TradingView Lightweight Charts equity curve
- [x] Active Positions Grid with PnL
- [x] Swarm Control panel with agent statuses
- [x] Stats Bar (NAV, positions, trades, alpha hits, swarm status)
- [x] Positions page with tabs (open positions / trade history)
- [x] Settings/Config page (AI models, wallets, execution params, chains, execution stack)
- [x] Sidebar navigation (OVERWATCH, POSITIONS, CONFIG)
- [x] WebSocket integration for real-time updates
- [x] CRT scanline overlay, neon glows, Orbitron/JetBrains Mono fonts

## Prioritized Backlog

### P0 - Critical (Next)
- [ ] Fix OpenRouter API key (currently returns 401 - user account issue)
- [ ] Wire real wallet transactions (LI.FI MCP for cross-chain routing)
- [ ] Pimlico gasless execution (EIP-7702)
- [ ] Flashbots MEV protection

### P1 - Important
- [ ] Wallet-based authentication
- [ ] Real portfolio tracking from on-chain data
- [ ] Stop-loss and take-profit automation
- [ ] Token watchlist / manual trade entry
- [ ] Historical PnL tracking with real equity curve

### P2 - Nice to Have
- [ ] TinyClaw integration for isolated agent workspaces
- [ ] On-chain event listeners for real-time liquidity pool detection
- [ ] Private RPC endpoint configuration
- [ ] Agent parameter tuning from UI
- [ ] Discord/Telegram notification integration
- [ ] Mobile responsive layout

## Next Tasks
1. Resolve OpenRouter API key authentication
2. Integrate LI.FI MCP for real cross-chain routing
3. Set up Pimlico for gasless execution
4. Add real wallet balance tracking
5. Implement real trade execution (Phase 2)
