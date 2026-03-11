# 4-Week Extended Validation - Quick Start

This is the **final validation step** before live deployment. The bot will run for 28 consecutive days on Gate.io testnet to validate performance matches backtest expectations.

---

## ⚡ Quick Start

### 1. Prerequisites

Ensure you have:
- ✅ Completed parameter optimization (tasks 5.1-5.4)
- ✅ Trained ML models (tasks 7.1-7.12)
- ✅ Configured bot with optimized parameters (task 9.10)
- ✅ Gate.io testnet account with API credentials
- ✅ Supabase database with tables created

### 2. Set Environment Variables

Add to your `.env` file:

```bash
# Gate.io Testnet
GATEIO_TESTNET_API_KEY=your_testnet_api_key
GATEIO_TESTNET_SECRET_KEY=your_testnet_secret_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# LLM APIs (if Context Agent enabled)
OPENROUTER_API_KEY=your_openrouter_key
PERPLEXITY_API_KEY=your_perplexity_key
```

### 3. Configure Bot

Generate optimized configuration:

```bash
python configure_optimized_bot.py
```

This creates `optimized_config.json` with all optimized parameters.

### 4. Test the System (Optional)

Run a quick 2-day test to verify everything works:

```bash
python run_quick_validation.py
```

### 5. Run Full Validation

Start the 28-day validation:

```bash
python run_extended_validation.py
```

**⚠️ Important:** The bot will run for 28 consecutive days. Do not interrupt unless absolutely necessary.

---

## 📊 What Happens

### During Validation

The bot will:
- Execute real trades on Gate.io testnet (minimum 50 trades)
- Track performance daily (win rate, profit factor, Sharpe ratio, etc.)
- Monitor for anomalies and edge cases
- Compare performance to backtest expectations
- Generate daily snapshots and logs

### After 28 Days

The system generates a comprehensive validation report with:
- Demo trading results
- Performance comparison vs backtest
- Edge case analysis
- **Go/No-Go recommendation** for live deployment
- Risk assessment and recommended capital

---

## 🔍 Monitoring Progress

### Real-Time Logs

```bash
tail -f logs/extended_validation_*.log
```

### Database Queries

```sql
-- Daily performance
SELECT * FROM performance_metrics 
WHERE metric_type = 'daily_snapshot'
ORDER BY timestamp DESC;

-- Recent trades
SELECT * FROM trades 
ORDER BY timestamp DESC 
LIMIT 20;

-- Edge cases
SELECT * FROM edge_cases 
WHERE resolution_status = 'open';
```

---

## ✅ Success Criteria

For a **GO** decision, the bot must achieve:

| Metric | Threshold |
|--------|-----------|
| Win Rate Variance | ±10% of backtest |
| Profit Factor Variance | ±20% of backtest |
| Max Drawdown | Not exceed backtest by >5% |
| Edge Case Resolution | >90% resolved |
| Total Trades | Minimum 50 trades |

---

## 📁 Output Files

After validation completes:

```
validation_reports/
└── validation_report_YYYYMMDD_HHMMSS.json

logs/
└── extended_validation_YYYYMMDD.log
```

---

## 🚨 Alerts

The system will alert if:
- Rolling 7-day win rate drops below 40%
- Rolling 7-day drawdown exceeds 15%
- Circuit breaker triggers (3 consecutive failures)
- Edge cases detected

---

## 📚 Documentation

For detailed information, see:
- **`EXTENDED_VALIDATION_GUIDE.md`** - Complete user guide
- **`TASK_9.11_EXTENDED_VALIDATION_SUMMARY.md`** - Technical details
- **`CONFIGURATION_GUIDE.md`** - Bot configuration guide

---

## 🆘 Troubleshooting

### No trades executed?
- Check Gate.io testnet balance
- Verify Bayesian threshold is not too high (should be ~0.65)
- Check market conditions

### Performance tracking errors?
- Verify Supabase connection
- Ensure database tables exist
- Check credentials in `.env`

### Circuit breaker triggered?
- Review logs to understand failures
- Check edge cases table
- May need to adjust parameters

---

## 🎯 Next Steps

### If GO Decision:
1. Review validation report thoroughly
2. Prepare for live deployment
3. Set up live exchange account
4. Start with recommended capital and limits

### If NO_GO Decision:
1. Identify root causes
2. Re-optimize parameters if needed
3. Fix identified edge cases
4. Run another validation cycle

---

## ⚠️ Important Notes

- **Do not interrupt** the 28-day validation unless absolutely necessary
- **Monitor daily** to catch issues early
- **Review edge cases** promptly
- **Take the validation seriously** - it's your final check before live trading

---

## 🚀 Ready to Start?

```bash
# 1. Configure bot
python configure_optimized_bot.py

# 2. Test (optional)
python run_quick_validation.py

# 3. Run full validation
python run_extended_validation.py
```

**Good luck! The bot is almost ready for live trading! 🎉**
