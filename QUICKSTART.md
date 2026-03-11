# 🚀 Quick Start Guide

## Get Up and Running in 10 Minutes

### Step 1: Clone and Setup (2 minutes)

```bash
# Extract the archive
tar -xzf autonomous-trading-bot.tar.gz
cd autonomous-trading-bot

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure (5 minutes)

```bash
# Copy environment template
cp .env.example .env

# Edit with your API keys
nano .env  # or use your favorite editor
```

**Minimum required:**
- `BINANCE_API_KEY` and `BINANCE_API_SECRET` (read-only permissions)
- `PERPLEXITY_API_KEY` (for Context Agent)
- `OPENROUTER_API_KEY` (for BigBrother chat)
- `SUPABASE_URL` and `SUPABASE_KEY` (or use local PostgreSQL)

### Step 3: Run Paper Trading (3 minutes)

```bash
# Start the bot in paper trading mode
python -m src.main --mode paper

# In another terminal, start the web interface
cd frontend && npm install && npm start

# Access dashboard at http://localhost:3000
```

## What Happens Next?

The bot will:
1. **Every 5 minutes**: Scan 150+ crypto pairs
2. **Identify**: High-probability breakouts and momentum plays
3. **Execute**: Paper trades (simulated) with proper risk management
4. **Report**: All decisions in logs and database

## Monitoring

- **Logs**: `tail -f logs/bot.log`
- **Dashboard**: http://localhost:3000
- **Grafana**: http://localhost:3001 (if using Docker)
- **API Docs**: http://localhost:8000/docs

## Next Steps

1. **Run for 24 hours** to see the bot in action
2. **Review decisions** in the dashboard
3. **Chat with BigBrother** to understand why trades were taken
4. **Adjust parameters** in `.env` based on your risk tolerance
5. **Backtest** on historical data (see BACKTESTING.md)
6. **Paper trade** for 3+ months before considering live mode

## Troubleshooting

### "No module named 'src'"
```bash
export PYTHONPATH=/path/to/autonomous-trading-bot:$PYTHONPATH
```

### "Connection refused" to database
```bash
# Start local PostgreSQL or check Supabase credentials
docker-compose up postgres -d
```

### "API key invalid"
- Check your exchange API keys have correct permissions
- Ensure keys are for the correct exchange (Binance vs Gate.io vs KuCoin)

### "Rate limit exceeded"
- Reduce `CYCLE_INTERVAL_SECONDS` to 600 (10 minutes)
- Check exchange API rate limits

## Safety Reminders

⚠️ **NEVER ENABLE LIVE MODE WITHOUT:**
1. 3+ months successful paper trading
2. Verified performance matches expectations
3. Understanding of all risks
4. Capital you can afford to lose
5. Starting with tiny position sizes ($50-100)

## Support

- GitHub Issues: https://github.com/yourusername/autonomous-trading-bot/issues
- Documentation: See `docs/` folder
- Examples: See `examples/` folder

---

**Happy Trading! 🚀**
