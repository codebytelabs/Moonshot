"""
DEMO TRADING SESSION — Gate.io Sandbox + Paper Trading Engine
Runs the full bot pipeline with real market data and simulated orders.
Uses shorter cycle intervals and lower thresholds for demonstration.
"""
import asyncio
import sys
import os
import signal
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import get_settings
from src.logger import setup_logging
from src.redis_client import RedisClient
from src.supabase_client import SupabaseStore
from src.exchange_ccxt import ExchangeConnector
from src.watcher import WatcherAgent
from src.analyzer import AnalyzerAgent
from src.risk_manager import RiskManager
from src.bayesian_engine import BayesianDecisionEngine
from src.position_manager import PositionManager
from loguru import logger


async def demo_session():
    """Run a complete demo trading session with real market data."""
    s = get_settings()
    setup_logging(debug=True)

    print()
    print("=" * 70)
    print("  🎯 MOONSHOT DEMO TRADING SESSION")
    print("  Using: Gate.io Sandbox (real market data + paper trading)")
    print("=" * 70)
    print()

    # ── Initialize Components ─────────────────────────────────────────────
    
    # Redis
    redis = RedisClient(s.redis_url, s.redis_password)
    await redis.connect()
    logger.info("✅ Redis connected")
    
    # Supabase
    store = SupabaseStore(s.supabase_url, s.supabase_anon_key)
    logger.info("✅ Supabase connected")
    
    # Exchange — Gate.io Sandbox (public API for real market data)
    exchange = ExchangeConnector(
        name="gateio",
        sandbox=True,  # Use sandbox for real market data feeds
    )
    await exchange.initialize()
    logger.info(f"✅ Gate.io sandbox loaded — {len(exchange.exchange.markets)} markets")
    
    # Agents
    watcher = WatcherAgent(
        exchange=exchange,
        redis=redis,
        store=store,
        min_volume_24h_usd=500_000,  # Lower threshold for demo
        top_n=30,  # More candidates
    )
    
    analyzer = AnalyzerAgent(
        exchange=exchange,
        redis=redis,
        store=store,
        timeframes=["5m", "15m", "1h"],  # Fewer timeframes for speed
        min_score=55.0,  # Lower threshold for demo — get more setups
        top_n=10,
    )
    
    # Risk & Position
    risk = RiskManager(s)
    engine = BayesianDecisionEngine(store=store, mode="normal")
    pm = PositionManager(
        exchange=exchange,
        settings=s,
        store=store,
        paper_mode=True,  # Always paper for demo
    )
    
    # ── Run Demo Cycles ──────────────────────────────────────────────────
    max_cycles = 3
    results = {
        "cycles_run": 0,
        "candidates_found": 0,
        "setups_found": 0,
        "decisions_made": 0,
        "positions_opened": 0,
        "positions_data": [],
        "watcher_details": [],
        "analyzer_details": [],
        "decision_details": [],
        "errors": [],
    }
    
    for cycle in range(1, max_cycles + 1):
        print()
        print(f"{'─' * 60}")
        print(f"  📡 CYCLE {cycle}/{max_cycles}")
        print(f"{'─' * 60}")
        t0 = time.monotonic()
        
        try:
            # 1. WATCHER: Scan market
            print(f"\n  [1/4] 🔭 Watcher scanning...")
            candidates = await watcher.scan()
            results["candidates_found"] += len(candidates) if candidates else 0
            
            if candidates:
                print(f"       Found {len(candidates)} candidates")
                for c in candidates[:5]:
                    sym = c.get("symbol", "?")
                    score = c.get("score", 0)
                    vol = c.get("volume_24h_usd", 0) or c.get("quoteVolume", 0) or 0
                    print(f"         {sym:<15} score={score:.1f}  vol=${vol:,.0f}")
                    results["watcher_details"].append({
                        "symbol": sym, "score": score, "volume": vol
                    })
                if len(candidates) > 5:
                    print(f"         ... and {len(candidates) - 5} more")
            else:
                print("       No candidates found")
                continue
            
            # 2. ANALYZER: Deep TA
            print(f"\n  [2/4] 📊 Analyzer running TA on {len(candidates)} candidates...")
            setups = await analyzer.analyze(candidates)
            results["setups_found"] += len(setups) if setups else 0
            
            if setups:
                print(f"       Found {len(setups)} setups passing analysis")
                for s_ in setups[:5]:
                    sym = s_.get("symbol", "?")
                    score = s_.get("ta_score", 0)
                    setup_type = s_.get("setup_type", "?")
                    entry = s_.get("entry_zone", {}).get("entry", 0)
                    sl = s_.get("entry_zone", {}).get("stop_loss", 0)
                    print(f"         {sym:<15} TA={score:.1f}  type={setup_type}  entry=${entry:.4f}  SL=${sl:.4f}")
                    results["analyzer_details"].append({
                        "symbol": sym, "ta_score": score, "setup_type": setup_type
                    })
            else:
                print("       No setups passed analysis")
                continue
            
            # 3. BAYESIAN: Decide
            print(f"\n  [3/4] 🧠 Bayesian engine evaluating {len(setups)} setups...")
            risk.set_open_positions(pm.get_open_positions())
            decisions = engine.batch_decide(setups)
            results["decisions_made"] += len(decisions) if decisions else 0
            
            if decisions:
                print(f"       Made {len(decisions)} entry decisions")
                for d in decisions[:5]:
                    sym = d.get("symbol", "?")
                    post = d.get("posterior", 0)
                    action = d.get("action", "?")
                    print(f"         {sym:<15} posterior={post:.3f}  action={action}")
                    results["decision_details"].append({
                        "symbol": sym, "posterior": post, "action": action
                    })
            else:
                print("       No entry decisions (all below threshold)")
                continue
            
            # 4. EXECUTE: Paper trades
            print(f"\n  [4/4] 💰 Executing paper trades...")
            for decision in decisions:
                symbol = decision["symbol"]
                can_open, reason = risk.can_open_position(symbol, decision)
                if not can_open:
                    print(f"         ⛔ {symbol}: Risk blocked — {reason}")
                    continue
                
                entry_zone = decision.get("entry_zone", {})
                size = risk.position_size_usd(
                    entry_price=entry_zone.get("entry", 0),
                    stop_loss=entry_zone.get("stop_loss", 0),
                    posterior=decision.get("posterior", 0.65),
                )
                if size < 10:
                    print(f"         ⚠️  {symbol}: Position size too small (${size:.2f})")
                    continue
                
                pos = await pm.open_position(
                    symbol=symbol,
                    size_usd=size,
                    entry_zone=entry_zone,
                    setup_type=decision.get("setup_type", "unknown"),
                    posterior=decision.get("posterior", 0),
                )
                if pos:
                    results["positions_opened"] += 1
                    results["positions_data"].append(pos.to_dict())
                    print(f"         ✅ OPENED {symbol}")
                    print(f"            Entry: ${pos.entry_price:.6f}")
                    print(f"            Size:  ${pos.notional_usd:.2f}")
                    print(f"            Stop:  ${pos.stop_loss:.6f}")
                    print(f"            Take:  ${pos.take_profit:.6f}")
                    print(f"            R-risk: ${pos.entry_price - pos.stop_loss:.6f}")
            
            # 5. UPDATE: Price feed
            tickers = await exchange.fetch_tickers()
            await pm.update_prices(tickers)
            
        except Exception as e:
            logger.error(f"Cycle {cycle} error: {e}")
            results["errors"].append(str(e))
            import traceback
            traceback.print_exc()
        
        elapsed = time.monotonic() - t0
        results["cycles_run"] = cycle
        print(f"\n  ⏱  Cycle {cycle} completed in {elapsed:.1f}s")
    
    # ── Final Report ─────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  📋 DEMO SESSION REPORT")
    print("=" * 70)
    print(f"  Cycles run:        {results['cycles_run']}")
    print(f"  Candidates found:  {results['candidates_found']}")
    print(f"  Setups found:      {results['setups_found']}")
    print(f"  Decisions made:    {results['decisions_made']}")
    print(f"  Positions opened:  {results['positions_opened']}")
    print(f"  Errors:            {len(results['errors'])}")
    
    if results["positions_data"]:
        print(f"\n  {'─' * 50}")
        print(f"  OPEN POSITIONS:")
        for p in results["positions_data"]:
            sym = p.get("symbol", "?")
            entry = p.get("entry_price", 0)
            current = p.get("current_price", 0)
            pnl = p.get("unrealized_pnl", 0)
            notional = p.get("notional_usd", 0)
            r_mult = p.get("r_multiple", 0)
            print(f"    {sym:<15} Entry=${entry:.4f}  Current=${current:.4f}  "
                  f"PnL=${pnl:.2f}  Notional=${notional:.2f}  R={r_mult:.2f}")
    
    if results["errors"]:
        print(f"\n  ERRORS:")
        for e in results["errors"]:
            print(f"    ❌ {e}")
    
    # Validation
    print(f"\n  {'─' * 50}")
    pipeline_works = (
        results["candidates_found"] > 0 and
        results["cycles_run"] == max_cycles
    )
    full_pipeline = results["positions_opened"] > 0
    
    if full_pipeline:
        print("  🎉 FULL PIPELINE VALIDATED: Scan → Analyze → Decide → Trade")
        print("  ✅ Demo trading with real market data is WORKING!")
    elif pipeline_works:
        print("  ✅ PIPELINE WORKS: Market scanning and analysis functional")
        print("  ⚠️  No positions opened (thresholds may prevent entry)")
        print("     This is normal — the bot is conservative by design")
    else:
        print("  ❌ Pipeline issues detected — review errors above")
    
    print("=" * 70)
    
    # Cleanup
    await exchange.close()
    await redis.close()
    
    return results


if __name__ == "__main__":
    results = asyncio.run(demo_session())
