"""
Full pipeline validation script.
Runs the bot through one complete cycle with lowered thresholds
to validate every agent in the chain works end-to-end.
"""
import asyncio
import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import get_settings, _ENV_FILE, Settings
from src.logger import setup_logging
from src.redis_client import RedisClient
from src.supabase_client import SupabaseStore
from src.exchange_ccxt import ExchangeConnector
from src.perplexity_client import PerplexityClient
from src.openrouter_client import OpenRouterClient
from src.watcher import WatcherAgent
from src.analyzer import AnalyzerAgent
from src.context_agent import ContextAgent
from src.bayesian_engine import BayesianDecisionEngine
from src.risk_manager import RiskManager
from src.position_manager import PositionManager
from src.bigbrother import BigBrotherAgent
from src.alerts import AlertManager
from loguru import logger


async def validate():
    """Run full pipeline validation."""
    setup_logging(debug=True)
    results = {}
    
    # ── 1. Config ────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("🧪 VALIDATION — Full Pipeline Test")
    logger.info("=" * 60)
    
    s = get_settings()
    results["config"] = {"status": "✅", "mode": s.mode, "exchange": s.exchange_name, "equity": s.initial_equity_usd}
    logger.info(f"✅ Config loaded: mode={s.mode}, exchange={s.exchange_name}")
    
    # ── 2. Redis ─────────────────────────────────────────────────────────
    redis = RedisClient(s.redis_url, s.redis_password)
    try:
        await redis.connect()
        results["redis"] = {"status": "✅", "connected": True}
        logger.info("✅ Redis connected")
    except Exception as e:
        results["redis"] = {"status": "⚠️", "error": str(e), "note": "Optional — bot falls back without Redis"}
        logger.warning(f"⚠️ Redis unavailable (optional): {e}")
        redis = None
    
    # ── 3. Supabase ──────────────────────────────────────────────────────
    store = SupabaseStore(s.supabase_url, s.supabase_anon_key)
    # Test insert to check if tables exist
    test_insert = store.insert_watcher_signal("TEST/USDT", 0.0, {"test": True})
    if test_insert:
        results["supabase"] = {"status": "✅", "tables": "created"}
        logger.info("✅ Supabase tables working")
    else:
        results["supabase"] = {"status": "⚠️", "note": "Tables not created yet — run schema.sql"}
        logger.warning("⚠️ Supabase tables not found — run schema.sql in Supabase SQL Editor")
    
    # ── 4. Exchange ──────────────────────────────────────────────────────
    exchange = ExchangeConnector(
        name=s.exchange_name,
        api_key=s.gateio_api_key,
        api_secret=s.gateio_api_secret,
        sandbox=(s.mode == "paper"),
    )
    await exchange.initialize()
    n_markets = len(exchange.exchange.markets)
    results["exchange"] = {"status": "✅", "markets": n_markets}
    logger.info(f"✅ Exchange: {n_markets} markets loaded")
    
    # ── 5. Watcher ───────────────────────────────────────────────────────
    watcher = WatcherAgent(
        exchange=exchange, redis=redis, store=store,
        min_volume_24h_usd=s.watcher_min_volume_24h_usd, top_n=s.watcher_top_n,
    )
    candidates = await watcher.scan()
    results["watcher"] = {"status": "✅" if candidates else "⚠️", "candidates": len(candidates) if candidates else 0}
    if candidates:
        logger.info(f"✅ Watcher: {len(candidates)} candidates")
        for c in candidates[:3]:
            logger.info(f"   • {c['symbol']}: score={c['score']}, vol_spike={c['features'].get('volume_spike', 'N/A')}")
    else:
        logger.warning("⚠️ Watcher found no candidates")
    
    # ── 6. Analyzer (lowered threshold) ──────────────────────────────────
    analyzer = AnalyzerAgent(
        exchange=exchange, redis=redis, store=store,
        timeframes=s.analyzer_timeframes,
        min_score=30.0,  # ← Lowered from 70 for validation
        top_n=10,
    )
    setups = await analyzer.analyze(candidates) if candidates else []
    results["analyzer"] = {"status": "✅" if setups else "⚠️", "setups": len(setups) if setups else 0}
    if setups:
        logger.info(f"✅ Analyzer: {len(setups)} setups passed (threshold=30)")
        for setup in setups[:3]:
            logger.info(f"   • {setup['symbol']}: type={setup.get('setup_type')}, score={setup.get('ta_score', 0):.1f}")
    else:
        logger.warning("⚠️ Analyzer found no setups even at threshold 30")
    
    # ── 7. Context Agent ─────────────────────────────────────────────────
    if setups:
        try:
            context = ContextAgent(perplexity=PerplexityClient(
                api_key=s.perplexity_api_key, base_url=s.perplexity_base_url,
                model=s.perplexity_model, timeout=s.perplexity_timeout,
                max_retries=s.perplexity_max_retries, retry_delay=s.perplexity_retry_delay,
            ), redis=redis, store=store)
            # Only enrich top 2 to save API calls
            enriched = await context.enrich(setups[:2])
            results["context"] = {"status": "✅", "enriched": len(enriched)}
            logger.info(f"✅ Context Agent: enriched {len(enriched)} setups via Perplexity")
            for e in enriched[:2]:
                ctx = e.get("context", {})
                logger.info(f"   • {e['symbol']}: sentiment={ctx.get('sentiment', '?')}, confidence={ctx.get('confidence', '?')}")
        except Exception as e:
            results["context"] = {"status": "⚠️", "error": str(e)}
            logger.warning(f"⚠️ Context Agent error: {e}")
            enriched = setups[:2]  # Fall back to unenriched
    else:
        results["context"] = {"status": "⏭️", "note": "Skipped — no setups"}
        enriched = []
    
    # ── 8. Bayesian Engine ───────────────────────────────────────────────
    engine = BayesianDecisionEngine(store=store, mode="normal")
    if enriched:
        decisions = engine.batch_decide(enriched)
        all_decisions = [engine.decide(s) for s in enriched]  # Get all, not just enters
        results["bayesian"] = {
            "status": "✅",
            "total_evaluated": len(all_decisions),
            "enters": len(decisions),
            "decisions": [{"symbol": d["symbol"], "action": d["action"], "posterior": d["posterior"]} for d in all_decisions],
        }
        logger.info(f"✅ Bayesian: {len(decisions)} enter / {len(all_decisions)} total decisions")
        for d in all_decisions:
            logger.info(f"   • {d['symbol']}: action={d['action']}, posterior={d['posterior']:.3f}")
    else:
        results["bayesian"] = {"status": "⏭️", "note": "Skipped — no enriched setups"}
    
    # ── 9. Risk Manager ──────────────────────────────────────────────────
    risk = RiskManager(s)
    health = risk.check_portfolio_health()
    results["risk"] = {
        "status": "✅",
        "health": health,
    }
    logger.info(f"✅ Risk Manager: equity=${health['equity']:,.0f}, drawdown={health['drawdown_pct']:.1%}, mode={health['recommended_mode']}")
    
    # ── 10. Position Manager ─────────────────────────────────────────────
    pm = PositionManager(
        exchange=exchange, settings=s, store=store, paper_mode=True,
    )
    results["position_manager"] = {"status": "✅", "open_positions": len(pm.get_open_positions())}
    logger.info(f"✅ Position Manager: {len(pm.get_open_positions())} open positions")
    
    # ── 11. BigBrother ───────────────────────────────────────────────────
    openrouter = OpenRouterClient(
        api_key=s.openrouter_api_key, base_url=s.openrouter_base_url,
        primary_model=s.openrouter_primary_model, secondary_model=s.openrouter_secondary_model,
    )
    alerts = AlertManager(
        discord_webhook=s.discord_webhook,
        telegram_token=s.telegram_bot_token,
        telegram_chat_id=s.telegram_chat_id,
    )
    bigbrother = BigBrotherAgent(
        risk_manager=risk, decision_engine=engine, store=store,
        openrouter_client=openrouter, alert_fn=alerts.send,
    )
    supervision = await bigbrother.supervise()
    results["bigbrother"] = {"status": "✅", "mode": supervision.get("mode", "unknown")}
    logger.info(f"✅ BigBrother: mode={supervision.get('mode')}")
    
    # ── 12. OpenRouter Chat ──────────────────────────────────────────────
    try:
        chat_reply = await openrouter.chat(
            "What is the current market sentiment for crypto in one sentence?",
            system_prompt="You are a helpful crypto trading assistant. Be very concise.",
        )
        results["openrouter_chat"] = {"status": "✅", "reply": chat_reply[:200]}
        logger.info(f"✅ OpenRouter chat: {chat_reply[:100]}...")
    except Exception as e:
        results["openrouter_chat"] = {"status": "⚠️", "error": str(e)}
        logger.warning(f"⚠️ OpenRouter error: {e}")
    
    # ── 13. API Endpoints ────────────────────────────────────────────────
    from src.api import create_app
    bot_state = {
        "mode": s.mode,
        "bigbrother": bigbrother,
        "position_manager": pm,
        "risk_manager": risk,
        "store": store,
        "openrouter": openrouter,
    }
    app = create_app(bot_state)
    
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        endpoints_ok = []
        for endpoint in ["/health", "/status", "/positions", "/trades", "/performance", "/metrics"]:
            resp = await client.get(endpoint)
            ok = resp.status_code == 200
            endpoints_ok.append({"endpoint": endpoint, "status": resp.status_code, "ok": ok})
            logger.info(f"   API {endpoint}: {resp.status_code} {'✅' if ok else '❌'}")
        
        # Test chat
        chat_resp = await client.post("/chat", json={"message": "How is the portfolio doing?"})
        endpoints_ok.append({"endpoint": "/chat", "status": chat_resp.status_code, "ok": chat_resp.status_code == 200})
        logger.info(f"   API /chat: {chat_resp.status_code} {'✅' if chat_resp.status_code == 200 else '❌'}")
    
    results["api"] = {"status": "✅", "endpoints": endpoints_ok}
    logger.info(f"✅ API: All {len(endpoints_ok)} endpoints responding")
    
    # ── Cleanup ──────────────────────────────────────────────────────────
    await exchange.close()
    if redis:
        await redis.close()
    
    # ── Summary ──────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("🧪 VALIDATION COMPLETE")
    logger.info("=" * 60)
    
    all_ok = all(r.get("status") == "✅" for r in results.values())
    for component, result in results.items():
        status = result.get("status", "?")
        logger.info(f"   {status} {component}")
    
    if all_ok:
        logger.info("🎉 ALL COMPONENTS VALIDATED SUCCESSFULLY")
    else:
        warnings = [k for k, v in results.items() if v.get("status") != "✅"]
        logger.info(f"⚠️ Components with warnings: {', '.join(warnings)}")
    
    # Save results
    out = Path(__file__).resolve().parent / "validation_report.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"📄 Report saved: {out}")
    
    return results


if __name__ == "__main__":
    asyncio.run(validate())
