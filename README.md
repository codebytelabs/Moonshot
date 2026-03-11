# 🚀 Autonomous AI Crypto Trading Bot

**Maximum Portfolio Growth via Multi-Agent AI System**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 Overview

A sophisticated multi-agent autonomous trading system designed to:
- **Scan** 150+ crypto pairs every 5 minutes for high-probability opportunities
- **Identify** breakouts and momentum plays using technical + semantic analysis
- **Execute** entries with 1-2% risk, let winners run 10x, 50x, 100x+
- **Manage** positions dynamically with pyramiding and trailing stops
- **Operate** 24/7 with full autonomy and BigBrother AI supervision

## 🎯 Target Performance

| Timeframe | Conservative | Aggressive | Peak Mania |
|-----------|--------------|-----------|------------|
| **Monthly** | +10-20% | +30-80% | +100-1000%+ |
| **Annual (Bull)** | +150-300% | +400-800% | +1000-2000%+ |
| **Win Rate** | 50-60% | 55-65% | 55-65% |
| **Max Drawdown** | <15% | <20% | <25% |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   BigBrother AI                          │
│         (Orchestration + Natural Language Chat)          │
└─────────────────────────────────────────────────────────┘
                          ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Watcher  │→ │ Analyzer │→ │ Context  │→ │ Bayesian │
│  Agent   │  │  Agent   │  │  Agent   │  │  Engine  │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
                          ▼
              ┌────────────────────────┐
              │  Position & Risk Mgr   │
              │  - Pyramiding          │
              │  - Trailing Stops      │
              │  - Multi-tier Exits    │
              └────────────────────────┘
                          ▼
              ┌────────────────────────┐
              │  CCXT (CEX Execution)  │
              │  Binance / Gate / KuCoin│
              └────────────────────────┘
```

## ✨ Key Features

### 1. Multi-Agent Intelligence
- **Watcher Agent**: Scans 150+ pairs for volume spikes, breakouts, momentum
- **Analyzer Agent**: Deep technical analysis with ML ensemble
- **Context Agent**: Perplexity-powered semantic analysis ("Why is this moving?")
- **Bayesian Engine**: Probabilistic decision fusion
- **BigBrother**: Meta-supervisor with natural language interface

### 2. Aggressive Position Management
- **Pyramiding**: Add to winners (max 2 additions per position)
- **Tiered Exits**: 25% at 2R, 25% at 5R, hold 50% as runner
- **Wide Trailing Stops**: 25-35% on runners to capture moonshots
- **Dynamic Sizing**: 1.5-3% per trade based on conviction

### 3. Portfolio Risk Controls
- Max 8 concurrent positions
- Max 20% single position exposure
- Max 20% portfolio drawdown limit
- Correlation monitoring
- Daily loss limits

### 4. Natural Language Interface
- Chat with BigBrother about portfolio status
- Ask "Why did you buy SOL?"
- Request strategy adjustments
- Real-time explanations of decisions

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)
- Exchange API keys (Binance, Gate.io, or KuCoin)
- Perplexity API key (for Context Agent)
- OpenRouter API key (for BigBrother chat)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/autonomous-trading-bot.git
cd autonomous-trading-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### Configuration

Edit `.env` file:

```bash
# Exchange Credentials
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here

# LLM APIs
PERPLEXITY_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here

# Database (use Supabase or local PostgreSQL)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Bot Configuration
MODE=paper  # paper, sim, or live
CYCLE_INTERVAL_SECONDS=300
MAX_CONCURRENT_POSITIONS=8
BASE_RISK_PER_TRADE_PCT=0.015
```

### Running

**Paper Trading (Recommended First):**
```bash
python -m src.main --mode paper
```

**With Docker:**
```bash
docker-compose up -d
```

**Access Web Interface:**
- Dashboard: http://localhost:8000
- Grafana Monitoring: http://localhost:3000
- Prometheus Metrics: http://localhost:9091

## 📊 Monitoring

### Grafana Dashboards
- Account equity curve
- Win rate (rolling 20 trades)
- Active positions
- R-multiple distribution
- API latency
- System health

### Prometheus Metrics
- `trades_total`: Total trades executed
- `active_positions`: Open positions count
- `account_equity_usd`: Current portfolio value
- `win_rate_rolling`: Rolling 20-trade win rate
- `avg_r_multiple_rolling`: Average R-multiple

## 🧪 Development Roadmap

### ✅ Phase 0: Foundation (Weeks 1-8)
- Data collection and backtesting framework
- Baseline strategy validation (50-55% win rate target)

### 🔄 Phase 1: Core Agents (Weeks 9-16)
- Watcher, Analyzer, Context agents
- Exchange integration via CCXT
- Paper trading mode

### 🔄 Phase 2: Decision & Execution (Weeks 17-24)
- Bayesian decision engine
- Position manager with pyramiding
- Trailing stop logic

### 🔄 Phase 3: Interface & Monitoring (Weeks 25-30)
- BigBrother supervisor
- React chatbot interface
- Prometheus + Grafana

### 🔄 Phase 4: ML Training (Weeks 31-38)
- Train ML ensemble on historical data
- A/B test Context Agent contribution
- Optional RL exit optimization

### 🔄 Phase 5: Paper Trading (Weeks 39-50)
- 3 months paper trading validation
- Performance monitoring
- Edge case fixes

### 🔄 Phase 6: Micro-Live (Weeks 51-58)
- Live trading with tiny positions ($50-100)
- Execution quality validation
- Slippage monitoring

### 🔄 Phase 7: Full Deployment (Weeks 59+)
- Scale to target position sizes
- Continuous optimization
- Ongoing model retraining

## 🔒 Safety & Risk Management

### Hard Limits
- ✅ Never risk >3% per trade (even with high conviction)
- ✅ Max 20% portfolio drawdown → halt trading
- ✅ Daily loss limit: -5% → pause new entries
- ✅ Max 8 concurrent positions
- ✅ Wide trailing stops protect runners (25-35%)

### Paper Trading First
**CRITICAL: Run in paper mode for 3+ months before going live**

- Validate performance matches backtest
- Identify and fix edge cases
- Build confidence in system decisions
- Monitor for drift or degradation

### Live Trading Guidelines
1. Start with 0.5% account risk per trade
2. Max $50-100 per position initially
3. Monitor every trade for first 2 weeks
4. Scale gradually only if performing well
5. Never enable withdrawal permissions on API keys

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Agent Specifications](docs/AGENTS.md)
- [Position Management](docs/POSITION_MANAGEMENT.md)
- [Risk Controls](docs/RISK_MANAGEMENT.md)
- [API Reference](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🛠️ Technology Stack

**Core:**
- Python 3.11+
- FastAPI (API & WebSocket)
- CCXT (Exchange connectivity)
- Pandas, NumPy (Data processing)

**ML & AI:**
- scikit-learn, XGBoost (ML ensemble)
- PyMC, ArviZ (Bayesian inference)
- LangChain, LangGraph (Multi-agent orchestration)
- OpenRouter (LLM access)
- Perplexity API (Semantic analysis)

**Data & Storage:**
- Supabase / PostgreSQL
- Redis (cache)
- Prometheus (metrics)

**Frontend:**
- React + TailwindCSS
- WebSocket (real-time updates)

**Deployment:**
- Docker + Docker Compose
- Kubernetes (optional)
- Grafana (monitoring)

## ⚠️ Disclaimer

**THIS SOFTWARE IS PROVIDED FOR EDUCATIONAL PURPOSES ONLY.**

- Trading cryptocurrencies involves substantial risk of loss
- Past performance does not guarantee future results
- Never trade with money you cannot afford to lose
- The authors are not responsible for any financial losses
- This is not financial advice
- Always do your own research and consult professionals

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📧 Contact

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/autonomous-trading-bot/issues)
- Discord: [Join our community](https://discord.gg/yourserver)

## 🙏 Acknowledgments

- Built on research from TradingAgents (UCLA/MIT)
- Inspired by institutional multi-agent trading systems
- Thanks to the open-source crypto trading community

---

**⚡ Build it. Test it. Deploy it. Profit. ⚡**
