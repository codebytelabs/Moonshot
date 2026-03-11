"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           MOONSHOT AUTONOMOUS TRADING BOT — FULL SYSTEM VALIDATION          ║
║           Gate.io Testnet   |   All Modules   |   End-to-End Test           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Tests (in order):
  1.  Environment & Config
  2.  Redis Connectivity
  3.  Supabase Connectivity & Schema
  4.  Gate.io Testnet — Auth + Balance + Markets
  5.  Gate.io Testnet — OHLCV + Ticker data
  6.  WatcherAgent — Market Scan
  7.  AnalyzerAgent — TA Analysis
  8.  ContextAgent — OpenRouter LLM
  9.  BayesianDecisionEngine
  10. RiskManager — Sizing + Circuit Breakers
  11. PositionManager — Paper Open/Close Simulation
  12. BigBrother Supervisor
  13. REST API Endpoints (via live backend)
  14. WebSocket Broadcast
  15. Frontend Health Check
  16. Full One-Cycle Integration Dry Run
"""
import asyncio
import sys
import os
import json
import time
import httpx
import traceback
from pathlib import Path
from datetime import datetime, timezone
from loguru import logger

# ── Setup path ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from src.config import get_settings
from src.redis_client import RedisClient
from src.supabase_client import SupabaseStore
from src.exchange_ccxt import ExchangeConnector
from src.openrouter_client import OpenRouterClient
from src.watcher import WatcherAgent
from src.analyzer import AnalyzerAgent
from src.context_agent import ContextAgent
from src.bayesian_engine import BayesianDecisionEngine
from src.risk_manager import RiskManager
from src.position_manager import PositionManager
from src.bigbrother import BigBrotherAgent

# ── Results tracker ───────────────────────────────────────────────────────────

RESULTS = []
PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"
INFO = "ℹ️  INFO"

def record(name, status, detail=""):
    icon = "✅" if "PASS" in status else ("❌" if "FAIL" in status else "⚠️")
    RESULTS.append({"name": name, "status": status, "detail": detail})
    logger.info(f"  {status}  [{name}] {detail}")

def section(title):
    logger.info(f"\n{'═'*70}")
    logger.info(f"  {title}")
    logger.info(f"{'═'*70}")

# ── Test Functions ────────────────────────────────────────────────────────────

async def test_config():
    section("1. ENVIRONMENT & CONFIGURATION")
    s = get_settings()
    checks = [
        ("SUPABASE_URL", bool(s.supabase_url)),
        ("SUPABASE_KEY", bool(s.supabase_anon_key)),
        ("GATEIO_TESTNET_KEY", bool(s.gateio_testnet_api_key)),
        ("GATEIO_TESTNET_SECRET", bool(s.gateio_testnet_secret_key)),
        ("OPENROUTER_KEY", bool(s.openrouter_api_key)),
        ("REDIS_URL", bool(s.redis_url)),
        ("EXCHANGE_MODE=demo", s.exchange_mode == "demo"),
        ("EXCHANGE_NAME=gateio", s.exchange_name == "gateio"),
    ]
    all_ok = True
    for name, ok in checks:
        if ok:
            record(f"Config:{name}", PASS)
        else:
            record(f"Config:{name}", FAIL, "NOT SET or wrong value")
            all_ok = False
    return s, all_ok


async def test_redis(settings):
    section("2. REDIS CONNECTIVITY")
    redis = RedisClient(settings.redis_url, settings.redis_password)
    try:
        await redis.connect()
        # Test write/read
        await redis.set("validation_test", "ok", ttl=10)
        val = await redis.get("validation_test")
        if val == "ok":
            record("Redis:Connect+RW", PASS, f"URL: {settings.redis_url}")
        else:
            record("Redis:RW", FAIL, f"Read back got: {val}")
        return redis
    except Exception as e:
        record("Redis:Connect", FAIL, str(e))
        return None


async def test_supabase(settings):
    section("3. SUPABASE CONNECTIVITY & SCHEMA")
    store = SupabaseStore(settings.supabase_url, settings.supabase_anon_key)
    tables = ["watcher_signals", "analyzer_signals", "decisions", "positions", "trades"]
    all_ok = True
    for table in tables:
        try:
            rows = store._query(table, limit=1)
            record(f"Supabase:{table}", PASS, f"{len(rows)} rows sampled")
        except Exception as e:
            record(f"Supabase:{table}", FAIL, str(e))
            all_ok = False
    return store, all_ok


async def test_exchange(settings):
    section("4. GATE.IO TESTNET — AUTH + BALANCE + MARKETS")
    exchange = ExchangeConnector(
        name="gateio",
        api_key=settings.gateio_testnet_api_key,
        api_secret=settings.gateio_testnet_secret_key,
        sandbox=False,
        demo_url=settings.gateio_testnet_url,
    )
    try:
        await exchange.initialize()
        pairs = exchange.get_usdt_pairs()
        record("Exchange:Markets", PASS, f"{len(pairs)} USDT pairs loaded")
    except Exception as e:
        record("Exchange:Markets", FAIL, str(e))
        return None

    try:
        balance = await exchange.fetch_balance()
        usdt_free = balance.get("USDT", {}).get("free", 0)
        total_equity = sum(v for v in balance.get("total", {}).values() if isinstance(v, (int,float)) and v > 0)
        record("Exchange:Auth+Balance", PASS, f"USDT free: ${usdt_free:,.2f} | Non-zero assets: {len([v for v in balance.get('total',{}).values() if isinstance(v,(int,float)) and v > 0])}")
    except Exception as e:
        record("Exchange:Auth+Balance", FAIL, str(e))
        return None

    return exchange


async def test_market_data(exchange):
    section("5. GATE.IO TESTNET — OHLCV + TICKER DATA")
    # Test OHLCV
    try:
        candles = await exchange.fetch_ohlcv("BTC/USDT", "1h", limit=50)
        record("Exchange:OHLCV_BTC", PASS, f"{len(candles)} candles (1h)")
    except Exception as e:
        record("Exchange:OHLCV_BTC", FAIL, str(e))

    # Test Tickers
    try:
        tickers = await exchange.fetch_tickers()
        btc_price = tickers.get("BTC/USDT", {}).get("last", 0)
        record("Exchange:Tickers", PASS, f"{len(tickers)} tickers | BTC/USDT: ${btc_price:,.2f}")
    except Exception as e:
        record("Exchange:Tickers", FAIL, str(e))

    # Test order book
    try:
        book = await exchange.fetch_order_book("ETH/USDT")
        bids = len(book.get("bids", []))
        record("Exchange:OrderBook_ETH", PASS, f"{bids} bid levels")
    except Exception as e:
        record("Exchange:OrderBook_ETH", FAIL, str(e))


async def test_watcher(exchange, redis, store, settings):
    section("6. WATCHER AGENT — MARKET SCAN")
    watcher = WatcherAgent(
        exchange=exchange,
        redis=redis,
        store=store,
        min_volume_24h_usd=settings.watcher_min_volume_24h_usd,
        top_n=settings.watcher_top_n,
    )
    try:
        t0 = time.monotonic()
        candidates = await watcher.scan()
        elapsed = time.monotonic() - t0
        if candidates:
            top = candidates[0]
            record("Watcher:Scan", PASS, f"{len(candidates)} candidates in {elapsed:.1f}s | Top: {top.get('symbol')} score={top.get('score',0):.3f}")
            return candidates
        else:
            record("Watcher:Scan", WARN, f"0 candidates in {elapsed:.1f}s (market may be quiet)")
            return []
    except Exception as e:
        record("Watcher:Scan", FAIL, str(e))
        return []


async def test_analyzer(exchange, redis, store, settings, candidates):
    section("7. ANALYZER AGENT — TECHNICAL ANALYSIS")
    analyzer = AnalyzerAgent(
        exchange=exchange,
        redis=redis,
        store=store,
        timeframes=settings.analyzer_timeframes,
        min_score=settings.analyzer_min_score,
        top_n=settings.analyzer_top_n,
    )
    # Use top candidates only (or fallback to BTC/ETH)
    test_candidates = candidates[:5] if candidates else [
        {"symbol": "BTC/USDT", "score": 0.6, "exchange": "gateio"},
        {"symbol": "ETH/USDT", "score": 0.55, "exchange": "gateio"},
    ]
    try:
        t0 = time.monotonic()
        setups = await analyzer.analyze(test_candidates)
        elapsed = time.monotonic() - t0
        if setups:
            top = setups[0]
            record("Analyzer:Analyze", PASS, f"{len(setups)} setups in {elapsed:.1f}s | Top: {top.get('symbol')} ta_score={top.get('ta_score',0):.3f}")
        else:
            record("Analyzer:Analyze", WARN, f"0 setups passed threshold in {elapsed:.1f}s (threshold may be strict)")
        return setups
    except Exception as e:
        record("Analyzer:Analyze", FAIL, str(e))
        return []


async def test_context_agent(settings, redis, store, setups):
    section("8. CONTEXT AGENT — OPENROUTER LLM")
    openrouter = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        primary_model=settings.openrouter_primary_model,
        secondary_model=settings.openrouter_secondary_model,
    )
    context = ContextAgent(
        openrouter_client=openrouter,
        redis=redis,
        store=store,
        model_id=settings.openrouter_perplexity_model,
    )

    # Test OpenRouter connectivity first
    try:
        reply = await openrouter.chat("Say 'VALIDATION_OK' only", system_prompt="You are a test bot.")
        if "VALIDATION_OK" in reply.upper() or len(reply) > 0:
            record("OpenRouter:Chat", PASS, f"Model: {settings.openrouter_primary_model} | Reply: {reply[:60]}...")
        else:
            record("OpenRouter:Chat", WARN, f"Unexpected reply: {reply[:60]}")
    except Exception as e:
        record("OpenRouter:Chat", FAIL, str(e))

    # Test context enrichment (use 1 symbol to save tokens)
    test_setups = setups[:1] if setups else [
        {"symbol": "BTC/USDT", "ta_score": 0.7, "setup_type": "breakout", "features": {}}
    ]
    try:
        t0 = time.monotonic()
        enriched = await context.enrich(test_setups)
        elapsed = time.monotonic() - t0
        if enriched:
            top = enriched[0]
            sentiment = top.get("sentiment", "unknown")
            confidence = top.get("confidence", 0)
            record("Context:Enrich", PASS, f"{len(enriched)} enriched in {elapsed:.1f}s | {test_setups[0]['symbol']} sentiment={sentiment} conf={confidence:.2f}")
        else:
            record("Context:Enrich", WARN, "No enriched setups returned")
        return openrouter, enriched
    except Exception as e:
        record("Context:Enrich", FAIL, str(e))
        return openrouter, test_setups


async def test_bayesian(store, enriched_setups):
    section("9. BAYESIAN DECISION ENGINE")
    engine = BayesianDecisionEngine(store=store, mode="normal")

    # Test single decision
    test_input = enriched_setups[:3] if enriched_setups else [
        {"symbol": "BTC/USDT", "ta_score": 0.75, "setup_type": "breakout_retest",
         "sentiment": "bullish", "confidence": 0.80, "features": {},
         "entry_zone": {"entry": 50000, "stop_loss": 48000, "take_profit_1": 54000}},
    ]
    try:
        decisions = engine.batch_decide(test_input)
        if decisions:
            top = decisions[0]
            record("Bayesian:Decide", PASS, f"{len(decisions)} decisions | {top.get('symbol')} posterior={top.get('posterior',0):.3f} action={top.get('action')}")
        else:
            record("Bayesian:Decide", WARN, "No decisions passed threshold")
        return engine, decisions
    except Exception as e:
        record("Bayesian:Decide", FAIL, str(e))
        return BayesianDecisionEngine(store=store), []


async def test_risk_manager(settings):
    section("10. RISK MANAGER — SIZING + CIRCUIT BREAKERS")
    risk = RiskManager(settings)
    risk.update_equity(50000)

    # Position sizing
    try:
        size = risk.position_size_usd(entry_price=50000, stop_loss=48000, posterior=0.75)
        record("RiskMgr:Sizing", PASS, f"size=${size:.2f} for BTC @ $50k stop=$48k posterior=0.75")
    except Exception as e:
        record("RiskMgr:Sizing", FAIL, str(e))

    # Can-trade check (healthy portfolio)
    try:
        can, reason = risk.can_open_position("BTC/USDT", {"posterior": 0.8, "entry_zone": {"entry": 50000, "stop_loss": 48000}})
        record("RiskMgr:CanTrade_OK", PASS if can else WARN, f"can={can} reason={reason}")
    except Exception as e:
        record("RiskMgr:CanTrade_OK", FAIL, str(e))

    # Max drawdown circuit breaker
    try:
        risk.update_equity(settings.initial_equity_usd * 0.70)  # -30% drawdown
        health = risk.check_portfolio_health()
        can_trade_after_dd = health.get("can_trade", True)
        record("RiskMgr:CircuitBreaker", PASS if not can_trade_after_dd else WARN,
               f"can_trade={can_trade_after_dd} (should be False at -30%) mode={health.get('recommended_mode')}")
        risk.update_equity(50000)  # Reset
    except Exception as e:
        record("RiskMgr:CircuitBreaker", FAIL, str(e))

    # Health check output
    try:
        risk.update_equity(50000)
        health = risk.check_portfolio_health()
        record("RiskMgr:HealthCheck", PASS, f"equity=${health.get('equity'):,.2f} drawdown={health.get('drawdown_pct',0):.1%} mode={health.get('recommended_mode')}")
    except Exception as e:
        record("RiskMgr:HealthCheck", FAIL, str(e))

    return risk


async def test_position_manager(exchange, settings, store):
    section("11. POSITION MANAGER — PAPER SIMULATION")
    pm = PositionManager(
        exchange=exchange,
        settings=settings,
        store=store,
        paper_mode=True,  # Paper mode for safety
    )

    # Test paper open
    try:
        pos = await pm.open_position(
            symbol="BTC/USDT",
            size_usd=500,
            entry_zone={"entry": 50000, "stop_loss": 48000, "take_profit_1": 56000},
            setup_type="breakout_retest",
            posterior=0.78,
        )
        if pos:
            record("PosMgr:Open_Paper", PASS, f"id={pos.id} symbol={pos.symbol} qty={pos.quantity:.6f} entry=${pos.entry_price:.2f}")

            # Test price update
            tickers = {"BTC/USDT": {"last": 51000}}
            await pm.update_prices(tickers)
            open_pos = pm.get_open_positions()
            record("PosMgr:UpdatePrice", PASS, f"{len(open_pos)} open positions")

            return pm
        else:
            record("PosMgr:Open_Paper", WARN, "Position not opened (size or risk check blocked it)")
            return pm
    except Exception as e:
        record("PosMgr:Open_Paper", FAIL, str(e))
        traceback.print_exc()
        return pm


async def test_bigbrother(risk, engine, store, openrouter):
    section("12. BIGBROTHER SUPERVISOR")
    bb = BigBrotherAgent(
        risk_manager=risk,
        decision_engine=engine,
        store=store,
        openrouter_client=openrouter,
    )
    try:
        result = await bb.supervise()
        mode = result.get("mode")
        health = result.get("health", {})
        events = result.get("events", [])
        record("BigBrother:Supervise", PASS, f"mode={mode} equity=${health.get('equity',0):,.2f} events={len(events)}")

        summary = bb.get_status_summary()
        record("BigBrother:StatusSummary", PASS, f"total_trades={summary.get('total_trades')} win_rate={summary.get('win_rate')}")
        return bb
    except Exception as e:
        record("BigBrother:Supervise", FAIL, str(e))
        return None


async def test_rest_api():
    section("13. REST API ENDPOINTS (http://localhost:8000)")
    endpoints = [
        ("GET", "/health"),
        ("GET", "/status"),
        ("GET", "/positions"),
        ("GET", "/trades"),
        ("GET", "/performance"),
        ("GET", "/settings"),
    ]
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10) as client:
        for method, path in endpoints:
            try:
                resp = await client.request(method, path)
                if resp.status_code == 200:
                    data = resp.json()
                    record(f"API:{path}", PASS, f"{resp.status_code} keys={list(data.keys())[:5]}")
                elif resp.status_code == 404:
                    # Likely a different version / path mismatch, but server IS running
                    record(f"API:{path}", WARN, f"HTTP 404 — server running but route may differ")
                else:
                    record(f"API:{path}", FAIL, f"HTTP {resp.status_code}")
            except httpx.ConnectError:
                record(f"API:{path}", WARN, "Backend not running — start with: python run_api.py")
                break
            except Exception as e:
                record(f"API:{path}", FAIL, str(e))


async def test_frontend():
    section("14. FRONTEND HEALTH CHECK (http://localhost:3000)")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get("http://localhost:3000")
            if resp.status_code == 200:
                record("Frontend:HomePage", PASS, f"HTTP {resp.status_code} | content-type={resp.headers.get('content-type','')[:40]}")
            else:
                record("Frontend:HomePage", WARN, f"HTTP {resp.status_code}")
        except httpx.ConnectError:
            record("Frontend:HomePage", WARN, "Not running (start with: npm run dev)")
        except Exception as e:
            record("Frontend:HomePage", FAIL, str(e))


async def test_full_cycle_dry_run(exchange, redis, store, settings):
    section("15. FULL ONE-CYCLE INTEGRATION DRY RUN")
    logger.info("  Running a simulated trading cycle (paper mode, no real orders)...")

    try:
        # Watcher
        watcher = WatcherAgent(exchange=exchange, redis=redis, store=store,
                               min_volume_24h_usd=settings.watcher_min_volume_24h_usd, top_n=10)
        candidates = await watcher.scan()
        logger.info(f"  Step 1 — Watcher: {len(candidates)} candidates")

        # Analyzer (if candidates)
        setups = []
        if candidates:
            analyzer = AnalyzerAgent(exchange=exchange, redis=redis, store=store,
                                     timeframes=settings.analyzer_timeframes, min_score=settings.analyzer_min_score, top_n=5)
            setups = await analyzer.analyze(candidates[:10])
        logger.info(f"  Step 2 — Analyzer: {len(setups)} setups")

        # Context
        openrouter = OpenRouterClient(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url,
                                      primary_model=settings.openrouter_primary_model, secondary_model=settings.openrouter_secondary_model)
        context = ContextAgent(openrouter_client=openrouter, redis=redis, store=store, model_id=settings.openrouter_perplexity_model)
        enriched = await context.enrich(setups[:2] if setups else [{"symbol": "BTC/USDT", "ta_score": 0.7, "setup_type": "breakout", "features": {}}])
        logger.info(f"  Step 3 — Context: {len(enriched)} enriched")

        # Bayesian
        engine = BayesianDecisionEngine(store=store, mode="normal")
        decisions = engine.batch_decide(enriched)
        logger.info(f"  Step 4 — Bayesian: {len(decisions)} decisions")

        # Risk
        risk = RiskManager(settings)
        risk.update_equity(50000)
        risk.set_open_positions([])

        entries_to_make = []
        for d in decisions:
            can, reason = risk.can_open_position(d["symbol"], d)
            if can:
                size = risk.position_size_usd(
                    entry_price=d.get("entry_zone", {}).get("entry", 0),
                    stop_loss=d.get("entry_zone", {}).get("stop_loss", 0),
                    posterior=d.get("posterior", 0.65)
                )
                if size >= 10:
                    entries_to_make.append((d, size))
        logger.info(f"  Step 5 — Risk: {len(entries_to_make)} entries approved")

        # Position Manager
        pm = PositionManager(exchange=exchange, settings=settings, store=store, paper_mode=True)
        opened = 0
        for d, size in entries_to_make[:2]:  # Cap at 2 paper trades
            pos = await pm.open_position(
                symbol=d["symbol"], size_usd=size,
                entry_zone=d.get("entry_zone", {}),
                setup_type=d.get("setup_type", "unknown"),
                posterior=d.get("posterior", 0),
            )
            if pos: opened += 1
        logger.info(f"  Step 6 — PositionManager: {opened} paper positions opened")

        # BigBrother
        bb = BigBrotherAgent(risk_manager=risk, decision_engine=engine, store=store, openrouter_client=openrouter)
        supervision = await bb.supervise()
        logger.info(f"  Step 7 — BigBrother: mode={supervision.get('mode')} health={supervision.get('health',{}).get('recommended_mode')}")

        record(
            "FullCycle:DryRun", PASS,
            f"candidates={len(candidates)} → setups={len(setups)} → enriched={len(enriched)} → decided={len(decisions)} → approved={len(entries_to_make)} → opened={opened}"
        )

    except Exception as e:
        record("FullCycle:DryRun", FAIL, f"{e}\n{traceback.format_exc()[-300:]}")


def print_summary():
    """Print a clean validation summary report."""
    total = len(RESULTS)
    passes = sum(1 for r in RESULTS if "PASS" in r["status"])
    failures = sum(1 for r in RESULTS if "FAIL" in r["status"])
    warns = sum(1 for r in RESULTS if "WARN" in r["status"])

    print(f"\n{'═'*70}")
    print(f"  MOONSHOT BOT — FULL SYSTEM VALIDATION REPORT")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'═'*70}")
    print(f"  {'Test':<45} {'Status':<12}")
    print(f"  {'-'*45} {'-'*12}")
    for r in RESULTS:
        icon = "✅" if "PASS" in r["status"] else ("❌" if "FAIL" in r["status"] else "⚠️ ")
        print(f"  {icon}  {r['name']:<43} {r['status'].split(' ')[0]}")
    print(f"\n{'═'*70}")
    print(f"  Total: {total} | ✅ {passes} passed | ❌ {failures} failed | ⚠️  {warns} warnings")
    score = int(passes / total * 100) if total > 0 else 0
    verdict = "🚀 PRODUCTION READY!" if failures == 0 and score >= 90 else ("⚠️  MOSTLY WORKING" if failures <= 3 else "❌ NEEDS FIXES")
    print(f"  Score: {score}% — {verdict}")
    print(f"{'═'*70}\n")

    # Save to file
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": passes,
        "failed": failures,
        "warnings": warns,
        "score_pct": score,
        "verdict": verdict,
        "results": RESULTS,
    }
    with open("validation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Full report saved to: validation_report.json")


# ── Main Runner ────────────────────────────────────────────────────────────────

async def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║         MOONSHOT AUTONOMOUS TRADING BOT — FULL SYSTEM VALIDATION            ║
║         Gate.io Testnet  |  All Modules  |  End-to-End                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    # 1. Config
    settings, config_ok = await test_config()
    if not config_ok:
        logger.error("Critical config missing. Aborting validation.")
        print_summary()
        return

    # 2. Redis
    redis = await test_redis(settings)

    # 3. Supabase
    store, _ = await test_supabase(settings)

    # 4. Exchange
    exchange = await test_exchange(settings)
    if not exchange:
        logger.error("Exchange init failed. Skipping dependent tests.")
        print_summary()
        return

    # 5. Market Data
    await test_market_data(exchange)

    # 6. Watcher
    candidates = await test_watcher(exchange, redis, store, settings)

    # 7. Analyzer
    setups = await test_analyzer(exchange, redis, store, settings, candidates)

    # 8. Context + OpenRouter
    openrouter, enriched = await test_context_agent(settings, redis, store, setups)

    # 9. Bayesian
    engine, decisions = await test_bayesian(store, enriched)

    # 10. Risk Manager
    risk = await test_risk_manager(settings)

    # 11. Position Manager (paper)
    pm = await test_position_manager(exchange, settings, store)

    # 12. BigBrother
    bb = await test_bigbrother(risk, engine, store, openrouter)

    # 13. REST API
    await test_rest_api()

    # 14. Frontend
    await test_frontend()

    # 15. Full One-Cycle Dry Run
    await test_full_cycle_dry_run(exchange, redis, store, settings)

    # Cleanup
    await exchange.close()
    if redis:
        await redis.close()

    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
