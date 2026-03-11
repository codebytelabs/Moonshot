"""
FastAPI backend — REST endpoints + WebSocket for real-time updates.
All routes used by the Moonshot Trading Bot frontend.
"""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest

# These will be injected after initialization
_bot_state = {}
_ws_clients: list[WebSocket] = [
]  # /ws clients (dashboard)
_ws_signal_clients: list[WebSocket] = []  # /ws/signals clients
_start_time = time.time()
_pipeline_runs: list[dict] = []   # Ring buffer: last 50 cycle summaries


def create_app(bot_state: dict) -> FastAPI:
    """Create the FastAPI application with access to bot state."""
    global _bot_state
    _bot_state = bot_state

    app = FastAPI(title="Moonshot Trading Bot API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─────────────────────────────────────────────────────────────
    # CORE ENDPOINTS
    # ─────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        uptime = int(time.time() - _start_time)
        return {
            "status": "ok",
            "mode": _bot_state.get("mode", "unknown"),
            "uptime": uptime,
        }

    @app.get("/status")
    async def status():
        bigbrother = _bot_state.get("bigbrother")
        if bigbrother:
            return bigbrother.get_status_summary()
        return {"mode": _bot_state.get("mode", "unknown"), "message": "bot starting"}

    @app.get("/positions")
    async def positions():
        pm = _bot_state.get("position_manager")
        if pm:
            return {"positions": pm.get_open_positions()}
        return {"positions": []}

    @app.get("/trades")
    async def trades():
        store = _bot_state.get("store")
        if store:
            return {"trades": store.get_recent_trades(50)}
        return {"trades": []}

    @app.get("/performance")
    async def performance():
        store = _bot_state.get("store")
        risk = _bot_state.get("risk_manager")
        result = {}
        if risk:
            result["health"] = risk.check_portfolio_health()
        if store:
            result["recent_metrics"] = store.get_performance_history(7)
        return result

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return generate_latest().decode("utf-8")

    @app.get("/settings")
    async def get_settings_endpoint():
        """Return public settings (safe attributes only)."""
        s = _bot_state.get("settings")
        if not s:
            return {}
        return {
            "mode": s.mode,                          # fixed: was s.trading_mode
            "exchange": s.exchange_name,
            "exchange_mode": s.exchange_mode,
            "ai_models": {
                "primary": s.openrouter_primary_model,
                "secondary": s.openrouter_secondary_model,
                "news": s.openrouter_perplexity_model,
            },
            "risk": {
                "max_drawdown": s.max_drawdown_pct,
                "risk_per_trade": s.max_risk_per_trade_pct,
                "max_positions": s.max_positions,
                "daily_loss_limit": s.daily_loss_limit_pct,
            },
            "system": {
                "cycle_interval": s.cycle_interval_seconds,
                "watcher_top_n": s.watcher_top_n,
                "analyzer_top_n": s.analyzer_top_n,
                "initial_equity_usd": s.initial_equity_usd,
            },
        }

    # ─────────────────────────────────────────────────────────────
    # AGENT / PIPELINE MONITORING ENDPOINTS
    # ─────────────────────────────────────────────────────────────

    @app.get("/api/dashboard/overview")
    async def dashboard_overview():
        """Full dashboard snapshot: status + positions + recent trades + pipeline."""
        risk = _bot_state.get("risk_manager")
        pm = _bot_state.get("position_manager")
        store = _bot_state.get("store")
        bigbrother = _bot_state.get("bigbrother")

        health = risk.check_portfolio_health() if risk else {}
        positions = pm.get_open_positions() if pm else []
        trades = store.get_recent_trades(10) if store else []
        bb_summary = bigbrother.get_status_summary() if bigbrother else {}

        last_run = _pipeline_runs[-1] if _pipeline_runs else {}

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": health,
            "mode": bb_summary.get("mode", _bot_state.get("mode", "unknown")),
            "positions": positions,
            "open_count": len(positions),
            "recent_trades": trades,
            "trade_count": len(trades),
            "last_cycle": last_run,
            "pipeline_runs_count": len(_pipeline_runs),
            "uptime_seconds": int(time.time() - _start_time),
            # Agent live status
            "agents": {
                "watcher": {"status": "active", "last_candidates": last_run.get("candidates", 0)},
                "analyzer": {"status": "active", "last_setups": last_run.get("setups", 0)},
                "context": {"status": "active"},
                "bayesian": {"status": "active", "last_decisions": last_run.get("decisions", 0)},
                "risk_manager": {"status": "active", "can_trade": health.get("can_trade", True)},
                "position_manager": {"status": "active", "open": len(positions)},
                "bigbrother": {"status": "active", "mode": bb_summary.get("mode", "normal"),
                               "total_trades": bb_summary.get("total_trades", 0),
                               "win_rate": bb_summary.get("win_rate", 0)},
            },
            "recent_events": bb_summary.get("recent_events", []),
        }

    @app.get("/api/signals")
    async def api_signals(limit: int = 20):
        """Return latest watcher + analyzer signals from Supabase."""
        store = _bot_state.get("store")
        if not store:
            return {"signals": []}
        try:
            watcher = store._query("watcher_signals", order_by="created_at", limit=limit)
            analyzer = store._query("analyzer_signals", order_by="created_at", limit=limit)
            # Merge and sort by time
            all_signals = []
            for r in watcher:
                r["agent"] = "watcher"
                all_signals.append(r)
            for r in analyzer:
                r["agent"] = "analyzer"
                all_signals.append(r)
            all_signals.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return {"signals": all_signals[:limit]}
        except Exception as e:
            logger.error(f"api_signals error: {e}")
            return {"signals": []}

    @app.get("/api/dashboard/pipeline-runs")
    async def pipeline_runs_endpoint(limit: int = 10):
        """Return recent pipeline cycle summaries (from in-memory ring buffer)."""
        runs = list(reversed(_pipeline_runs[-limit:]))
        return {
            "runs": runs,
            "total": len(_pipeline_runs),
        }

    @app.post("/api/pipeline/run")
    async def trigger_pipeline_run():
        """Trigger an immediate trading cycle (next cycle runs ASAP)."""
        # Signal the bot to run soonest — set a flag captured by main loop
        _bot_state["trigger_immediate_cycle"] = True
        logger.info("🔄 Manual pipeline cycle triggered via API")
        return {"status": "triggered", "message": "Next cycle will run immediately"}

    @app.get("/api/agents/status")
    async def agents_status():
        """Per-agent status with detailed health info."""
        overview = await dashboard_overview()
        return {
            "timestamp": overview["timestamp"],
            "agents": overview["agents"],
            "mode": overview["mode"],
        }

    @app.get("/api/bigbrother/events")
    async def bigbrother_events(limit: int = 20):
        """Return BigBrother supervision events."""
        bigbrother = _bot_state.get("bigbrother")
        if not bigbrother:
            return {"events": []}
        events = bigbrother.events[-limit:] if bigbrother.events else []
        return {
            "events": list(reversed(events)),
            "mode": bigbrother.current_mode,
            "total_trades": len(bigbrother.trade_results),
        }

    # ─────────────────────────────────────────────────────────────
    # CHAT
    # ─────────────────────────────────────────────────────────────

    @app.post("/chat")
    async def chat(body: dict):
        """Chat with the bot via OpenRouter."""
        openrouter = _bot_state.get("openrouter")
        if not openrouter:
            return {"reply": "Chat not available — OpenRouter not configured"}
        prompt = body.get("message", "")
        if not prompt:
            return {"reply": "Empty message"}
        risk = _bot_state.get("risk_manager")
        context = ""
        if risk:
            health = risk.check_portfolio_health()
            context = (
                f"Portfolio: equity=${health['equity']:,.0f}, "
                f"drawdown={health['drawdown_pct']:.1%}, "
                f"mode={health['recommended_mode']}, "
                f"can_trade={health['can_trade']}"
            )
        system = (
            "You are the Moonshot autonomous trading bot assistant. "
            "You help the user understand bot activity, positions, and market conditions. "
            f"Current context: {context}"
        )
        try:
            reply = await openrouter.chat(prompt, system_prompt=system)
            return {"reply": reply}
        except Exception as e:
            return {"reply": f"Error: {e}"}

    # ─────────────────────────────────────────────────────────────
    # SYNC
    # ─────────────────────────────────────────────────────────────

    @app.post("/sync")
    async def sync_trades():
        """Trigger manual trade sync from exchange to Supabase."""
        asyncio.create_task(_sync_trades_logic())
        return {"status": "sync_started", "message": "Background sync initiated"}

    async def _sync_trades_logic():
        """Fetch trades from exchange and populate Supabase."""
        logger.info("🔄 SYNC: Starting trade synchronization...")
        exchange = _bot_state.get("exchange")
        store = _bot_state.get("store")

        if not exchange or not store:
            logger.error("❌ SYNC: Components not ready")
            return

        try:
            balance = await exchange.exchange.fetch_balance()
            held_assets = {
                asset for asset, amt in balance["total"].items()
                if amt > 0 and asset != "USDT"
            }
            all_pairs = exchange.get_usdt_pairs()
            relevant_pairs = [p for p in all_pairs if p.split("/")[0] in held_assets]

            logger.info(f"🔄 SYNC: {len(held_assets)} held assets → {len(relevant_pairs)} pairs")
            total_synced = 0

            for symbol in relevant_pairs:
                last_ts = store.get_latest_trade_time(symbol)
                since = last_ts + 1 if last_ts else None
                trades = await exchange.fetch_my_trades(symbol, since=since, limit=50)
                if not trades:
                    continue
                for t in trades:
                    if not t.get("id"):
                        continue
                    pnl = t.get("info", {}).get("pnl") or 0
                    store.insert_trade(
                        position_id=None,
                        symbol=t["symbol"],
                        side=t["side"],
                        price=t["price"],
                        quantity=t["amount"],
                        notional_usd=t["cost"],
                        trade_type="external_sync",
                        pnl=float(pnl) if pnl else 0,
                        exchange=exchange.name,
                        created_at=datetime.fromtimestamp(t["timestamp"] / 1000, timezone.utc).isoformat(),
                        exchange_trade_id=t["id"],
                    )
                    total_synced += 1
                if trades:
                    logger.info(f"   Synced {len(trades)} trades for {symbol}")

            logger.info(f"✅ SYNC: Completed. Total synced: {total_synced}")
        except Exception as e:
            logger.error(f"❌ SYNC: Failed: {e}")

    # ─────────────────────────────────────────────────────────────
    # WEBSOCKETS
    # ─────────────────────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        """Primary WebSocket — streams cycle updates to dashboard."""
        await ws.accept()
        _ws_clients.append(ws)
        logger.info(f"WebSocket /ws connected (total: {len(_ws_clients)})")
        try:
            while True:
                await ws.receive_text()  # keep-alive ping
        except WebSocketDisconnect:
            if ws in _ws_clients:
                _ws_clients.remove(ws)
            logger.info(f"WebSocket /ws disconnected (total: {len(_ws_clients)})")

    @app.websocket("/ws/signals")
    async def websocket_signals(ws: WebSocket):
        """Signals WebSocket — streams watcher/analyzer signals + BigBrother events."""
        await ws.accept()
        _ws_signal_clients.append(ws)
        logger.info(f"WebSocket /ws/signals connected (total: {len(_ws_signal_clients)})")
        # Send immediate snapshot on connect
        try:
            store = _bot_state.get("store")
            bigbrother = _bot_state.get("bigbrother")
            snapshot = {
                "type": "snapshot",
                "mode": _bot_state.get("mode", "unknown"),
                "pipeline_runs": _pipeline_runs[-5:],
                "recent_events": bigbrother.events[-5:] if bigbrother else [],
            }
            await ws.send_text(json.dumps(snapshot, default=str))
        except Exception as e:
            logger.warning(f"ws/signals snapshot error: {e}")

        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            if ws in _ws_signal_clients:
                _ws_signal_clients.remove(ws)
            logger.info(f"WebSocket /ws/signals disconnected (total: {len(_ws_signal_clients)})")

    return app


async def broadcast_ws(data: dict):
    """Broadcast cycle data to ALL connected WebSocket clients (/ws and /ws/signals)."""
    global _pipeline_runs

    # Store in ring buffer (keep last 50)
    run_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": data.get("cycle"),
        "mode": data.get("mode"),
        "candidates": data.get("candidates", 0),
        "setups": data.get("setups", 0),
        "decisions": data.get("entries", 0),
        "positions": len(data.get("positions", [])),
    }
    _pipeline_runs.append(run_record)
    if len(_pipeline_runs) > 50:
        _pipeline_runs.pop(0)

    message = json.dumps(data, default=str)
    all_clients = _ws_clients + _ws_signal_clients

    # Include agent status in signals broadcast
    signals_data = {**data, "type": "cycle_update", "pipeline_run": run_record}
    signals_message = json.dumps(signals_data, default=str)

    disconnected_main = []
    for ws in list(_ws_clients):
        try:
            await ws.send_text(message)
        except Exception:
            disconnected_main.append(ws)

    disconnected_signals = []
    for ws in list(_ws_signal_clients):
        try:
            await ws.send_text(signals_message)
        except Exception:
            disconnected_signals.append(ws)

    for ws in disconnected_main:
        if ws in _ws_clients:
            _ws_clients.remove(ws)
    for ws in disconnected_signals:
        if ws in _ws_signal_clients:
            _ws_signal_clients.remove(ws)
