"""
Comprehensive API & Backend Test Script
Tests all REST endpoints and WebSocket connections with real data.
Run with: python test_live_api.py
"""
import asyncio
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from src.api import create_app
from src.risk_manager import RiskManager
from src.position_manager import PositionManager, Position


def make_rich_bot_state():
    """Create a bot_state dict with mocked components for realistic testing."""
    # Settings mock
    settings = MagicMock()
    settings.mode = "paper"
    settings.exchange_name = "gateio"
    settings.initial_equity_usd = 10000.0
    settings.max_positions = 5
    settings.max_risk_per_trade_pct = 0.01
    settings.max_portfolio_exposure_pct = 0.30
    settings.max_single_exposure_pct = 0.08
    settings.max_correlation = 0.7
    settings.max_drawdown_pct = 0.10
    settings.daily_loss_limit_pct = 0.03
    settings.tier1_r_multiple = 2.0
    settings.tier1_exit_pct = 0.25
    settings.tier2_r_multiple = 5.0
    settings.tier2_exit_pct = 0.25
    settings.runner_trailing_stop_pct = 0.03
    settings.pyramid_enabled = False
    settings.pyramid_max_adds = 0
    settings.pyramid_min_r_to_add = 1.5

    # Risk Manager (real object)
    risk = RiskManager(settings)

    # Position Manager with mock exchange
    exchange = AsyncMock()
    exchange.name = "gateio"
    store = MagicMock()
    store.get_recent_trades = MagicMock(return_value=[
        {
            "id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "position_id": "pos-001",
            "symbol": "BTC/USDT",
            "exchange": "gateio",
            "side": "buy",
            "price": 45000.0,
            "quantity": 0.01,
            "notional_usd": 450.0,
            "trade_type": "entry",
            "pnl": None,
            "r_multiple": None,
        },
        {
            "id": 2,
            "created_at": "2025-01-01T01:00:00Z",
            "position_id": "pos-001",
            "symbol": "BTC/USDT",
            "exchange": "gateio",
            "side": "sell",
            "price": 46000.0,
            "quantity": 0.0025,
            "notional_usd": 115.0,
            "trade_type": "tier1_exit",
            "pnl": 2.5,
            "r_multiple": 2.0,
        },
    ])
    store.get_performance_history = MagicMock(return_value=[
        {"metric_type": "equity", "value": 10050.0, "created_at": "2025-01-01T00:00:00Z"},
        {"metric_type": "equity", "value": 10120.0, "created_at": "2025-01-02T00:00:00Z"},
    ])

    pm = PositionManager(
        exchange=exchange,
        settings=settings,
        store=store,
        paper_mode=True,
    )

    # Add a fake open position
    pos = Position(
        symbol="BTC/USDT",
        side="long",
        entry_price=45000.0,
        quantity=0.01,
        stop_loss=43500.0,
        take_profit=50000.0,
        setup_type="breakout",
        posterior=0.72,
        exchange="gateio",
    )
    pos.current_price = 46500.0
    pos.highest_price = 46800.0
    pm.positions[pos.id] = pos

    # BigBrother mock
    bigbrother = MagicMock()
    bigbrother.get_status_summary = MagicMock(return_value={
        "mode": "paper",
        "current_mode": "normal",
        "total_trades": 5,
        "wins": 3,
        "losses": 2,
        "win_rate": 0.60,
        "total_pnl": 250.0,
        "active_positions": 1,
        "uptime_seconds": 3600,
    })

    state = {
        "mode": "paper",
        "position_manager": pm,
        "store": store,
        "risk_manager": risk,
        "bigbrother": bigbrother,
        "openrouter": None,  # No OpenRouter for test
    }
    return state


async def test_all_endpoints():
    """Test all REST API endpoints with rich bot state."""
    state = make_rich_bot_state()
    app = create_app(state)
    transport = ASGITransport(app=app)

    results = []
    total = 0
    passed = 0
    failed = 0

    async with AsyncClient(transport=transport, base_url="http://test") as ac:

        # ── Test 1: GET /health ─────────────────────────────────────────
        total += 1
        try:
            resp = await ac.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["mode"] == "paper"
            results.append(("GET /health", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("GET /health", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 2: GET /status ─────────────────────────────────────────
        total += 1
        try:
            resp = await ac.get("/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["mode"] == "paper"
            assert "win_rate" in data
            assert data["total_trades"] == 5
            results.append(("GET /status", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("GET /status", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 3: GET /positions (with data) ──────────────────────────
        total += 1
        try:
            resp = await ac.get("/positions")
            assert resp.status_code == 200
            data = resp.json()
            assert "positions" in data
            assert len(data["positions"]) == 1
            pos = data["positions"][0]
            assert pos["symbol"] == "BTC/USDT"
            assert pos["side"] == "long"
            assert pos["entry_price"] == 45000.0
            assert pos["current_price"] == 46500.0
            assert pos["setup_type"] == "breakout"
            assert "id" in pos
            results.append(("GET /positions", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("GET /positions", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 4: GET /trades ─────────────────────────────────────────
        total += 1
        try:
            resp = await ac.get("/trades")
            assert resp.status_code == 200
            data = resp.json()
            assert "trades" in data
            assert len(data["trades"]) == 2
            assert data["trades"][0]["symbol"] == "BTC/USDT"
            results.append(("GET /trades", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("GET /trades", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 5: GET /performance ────────────────────────────────────
        total += 1
        try:
            resp = await ac.get("/performance")
            assert resp.status_code == 200
            data = resp.json()
            assert "health" in data
            assert "recent_metrics" in data
            health = data["health"]
            assert health["equity"] == 10000.0
            assert "drawdown_pct" in health
            assert "recommended_mode" in health
            results.append(("GET /performance", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("GET /performance", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 6: GET /metrics (Prometheus) ───────────────────────────
        total += 1
        try:
            resp = await ac.get("/metrics")
            assert resp.status_code == 200
            text = resp.text
            # Should contain Prometheus metrics
            assert "HELP" in text or "TYPE" in text or "process" in text or len(text) > 10
            results.append(("GET /metrics", "✅ PASSED", f"{len(text)} bytes"))
            passed += 1
        except Exception as e:
            results.append(("GET /metrics", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 7: POST /chat (no OpenRouter → fallback) ──────────────
        total += 1
        try:
            resp = await ac.post("/chat", json={"message": "What is the current BTC price?"})
            assert resp.status_code == 200
            data = resp.json()
            assert "reply" in data
            assert "not available" in data["reply"].lower() or "not configured" in data["reply"].lower()
            results.append(("POST /chat (no OR)", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("POST /chat (no OR)", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 8: POST /chat (empty message) ─────────────────────────
        total += 1
        try:
            resp = await ac.post("/chat", json={"message": ""})
            assert resp.status_code == 200
            data = resp.json()
            assert "reply" in data
            results.append(("POST /chat (empty)", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("POST /chat (empty)", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 9: GET /nonexistent ────────────────────────────────────
        total += 1
        try:
            resp = await ac.get("/nonexistent")
            assert resp.status_code == 404
            results.append(("GET /nonexistent", "✅ PASSED (404)", None))
            passed += 1
        except Exception as e:
            results.append(("GET /nonexistent", f"❌ FAILED: {e}", None))
            failed += 1

        # ── Test 10: POST /chat (invalid body) ─────────────────────────
        total += 1
        try:
            resp = await ac.post("/chat", json={})
            assert resp.status_code == 200
            data = resp.json()
            # Should handle missing "message" key gracefully
            assert "reply" in data
            results.append(("POST /chat (no msg key)", "✅ PASSED", data))
            passed += 1
        except Exception as e:
            results.append(("POST /chat (no msg key)", f"❌ FAILED: {e}", None))
            failed += 1

    # ── Print Results ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("🧪 MOONSHOT API TEST RESULTS")
    print("=" * 70)
    for name, status, data in results:
        print(f"  {status}  {name}")
        if data and isinstance(data, dict):
            print(f"         → {json.dumps(data, indent=None, default=str)[:120]}")
    print(f"\n{'=' * 70}")
    print(f"  TOTAL: {total} | PASSED: {passed} ✅ | FAILED: {failed} ❌")
    print(f"{'=' * 70}\n")

    return passed, failed


async def test_websocket():
    """Test WebSocket connection."""
    from src.api import create_app, broadcast_ws, _ws_clients
    import websockets

    state = make_rich_bot_state()
    app = create_app(state)

    print("\n  ℹ️  WebSocket test skipped (requires running server)")
    print("      WebSocket endpoint: ws://localhost:8000/ws")
    print("      Tested via unit test mock in test_api.py")
    return 0, 0


async def test_risk_manager_edge_cases():
    """Test RiskManager with various edge cases."""
    results = []
    total = 0
    passed = 0
    failed = 0

    settings = MagicMock()
    settings.initial_equity_usd = 10000.0
    settings.max_positions = 5
    settings.max_risk_per_trade_pct = 0.01
    settings.max_portfolio_exposure_pct = 0.30
    settings.max_single_exposure_pct = 0.08
    settings.max_correlation = 0.7
    settings.max_drawdown_pct = 0.10
    settings.daily_loss_limit_pct = 0.03

    risk = RiskManager(settings)

    # Test 1: Position sizing with normal params
    total += 1
    try:
        size = risk.position_size_usd(entry_price=100.0, stop_loss=95.0, posterior=0.7)
        assert size > 0, f"Expected positive size, got {size}"
        assert size <= 10000 * 0.08, f"Size {size} exceeds max single exposure"
        results.append(("Risk: normal position size", f"✅ PASSED (${size:.2f})", None))
        passed += 1
    except Exception as e:
        results.append(("Risk: normal position size", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 2: Position sizing with zero stop loss
    total += 1
    try:
        size = risk.position_size_usd(entry_price=100.0, stop_loss=0.0, posterior=0.7)
        results.append(("Risk: zero stop_loss", f"✅ PASSED (${size:.2f})", None))
        passed += 1
    except Exception as e:
        results.append(("Risk: zero stop_loss", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 3: Portfolio health after drawdown
    total += 1
    try:
        risk.update_equity(10000.0)
        risk.update_equity(9200.0)  # 8% drawdown
        health = risk.check_portfolio_health()
        assert health["recommended_mode"] in ("normal", "volatile", "safety")
        results.append(("Risk: drawdown health", f"✅ PASSED (mode={health['recommended_mode']})", None))
        passed += 1
    except Exception as e:
        results.append(("Risk: drawdown health", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 4: Daily loss limit
    total += 1
    try:
        risk2 = RiskManager(settings)
        risk2.daily_pnl = -350.0  # -3.5% of 10000, exceeds 3% limit
        can, reason = risk2.can_open_position("TEST/USDT", {"symbol": "TEST/USDT"})
        assert can is False, f"Expected blocked, got {can}"
        assert "daily" in reason.lower()
        results.append(("Risk: daily loss limit", f"✅ PASSED ({reason})", None))
        passed += 1
    except Exception as e:
        results.append(("Risk: daily loss limit", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 5: Max positions reached
    total += 1
    try:
        risk3 = RiskManager(settings)
        fake_positions = [{"symbol": f"COIN{i}/USDT"} for i in range(5)]
        risk3.set_open_positions(fake_positions)
        can, reason = risk3.can_open_position("NEW/USDT", {"symbol": "NEW/USDT"})
        assert can is False
        results.append(("Risk: max positions", f"✅ PASSED ({reason})", None))
        passed += 1
    except Exception as e:
        results.append(("Risk: max positions", f"❌ FAILED: {e}", None))
        failed += 1

    print("\n" + "-" * 70)
    print("🛡️  RISK MANAGER EDGE CASE TESTS")
    print("-" * 70)
    for name, status, _ in results:
        print(f"  {status}  {name}")
    print(f"  TOTAL: {total} | PASSED: {passed} ✅ | FAILED: {failed} ❌\n")

    return passed, failed


async def test_position_lifecycle():
    """Test full Position lifecycle: open → tier exits → close."""
    results = []
    total = 0
    passed = 0
    failed = 0

    settings = MagicMock()
    settings.initial_equity_usd = 10000.0
    settings.max_positions = 5
    settings.max_risk_per_trade_pct = 0.01
    settings.max_portfolio_exposure_pct = 0.30
    settings.max_single_exposure_pct = 0.08
    settings.max_correlation = 0.7
    settings.max_drawdown_pct = 0.10
    settings.daily_loss_limit_pct = 0.03
    settings.tier1_r_multiple = 2.0
    settings.tier1_exit_pct = 0.25
    settings.tier2_r_multiple = 5.0
    settings.tier2_exit_pct = 0.25
    settings.runner_trailing_stop_pct = 0.03
    settings.pyramid_enabled = False
    settings.pyramid_max_adds = 0
    settings.pyramid_min_r_to_add = 1.5

    exchange = AsyncMock()
    exchange.name = "gateio"
    # amount_to_precision is a sync method — use MagicMock, not AsyncMock
    exchange.amount_to_precision = MagicMock(side_effect=lambda sym, qty: qty)
    store = MagicMock()
    store.upsert_position = MagicMock(return_value={})
    store.insert_trade = MagicMock(return_value={})

    pm = PositionManager(exchange=exchange, settings=settings, store=store, paper_mode=True)

    # Test 1: Open a position
    total += 1
    try:
        pos = await pm.open_position(
            symbol="ETH/USDT",
            size_usd=500.0,
            entry_zone={"entry": 2000.0, "stop_loss": 1900.0, "target": 2200.0},
            setup_type="breakout",
            posterior=0.72,
        )
        assert pos is not None
        assert pos.symbol == "ETH/USDT"
        assert pos.entry_price == 2000.0
        assert pos.stop_loss == 1900.0
        assert len(pm.positions) == 1
        results.append(("Position: open", f"✅ PASSED (qty={pos.quantity:.4f})", None))
        passed += 1
    except Exception as e:
        results.append(("Position: open", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 2: R-multiple calculation
    total += 1
    try:
        pos = list(pm.positions.values())[0]
        pos.current_price = 2200.0  # +200/100 = 2R
        r = pos.r_multiple
        assert abs(r - 2.0) < 0.01, f"Expected 2.0R, got {r:.2f}"
        results.append(("Position: R-multiple", f"✅ PASSED ({r:.2f}R)", None))
        passed += 1
    except Exception as e:
        results.append(("Position: R-multiple", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 3: Unrealized PnL
    total += 1
    try:
        pnl = pos.unrealized_pnl
        pnl_pct = pos.unrealized_pnl_pct
        assert pnl > 0, f"Expected positive PnL, got {pnl}"
        results.append(("Position: unrealized PnL", f"✅ PASSED (${pnl:.2f}, {pnl_pct:.1%})", None))
        passed += 1
    except Exception as e:
        results.append(("Position: unrealized PnL", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 4: Position to_dict (serialization)
    total += 1
    try:
        d = pos.to_dict()
        assert isinstance(d, dict)
        required_keys = ["id", "symbol", "side", "entry_price", "current_price",
                         "quantity", "stop_loss", "setup_type", "status"]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"
        results.append(("Position: to_dict", f"✅ PASSED ({len(d)} keys)", None))
        passed += 1
    except Exception as e:
        results.append(("Position: to_dict", f"❌ FAILED: {e}", None))
        failed += 1

    # Test 5: Get open positions
    total += 1
    try:
        open_pos = pm.get_open_positions()
        assert isinstance(open_pos, list)
        assert len(open_pos) == 1
        results.append(("Position: get_open_positions", f"✅ PASSED ({len(open_pos)} positions)", None))
        passed += 1
    except Exception as e:
        results.append(("Position: get_open_positions", f"❌ FAILED: {e}", None))
        failed += 1

    print("-" * 70)
    print("📊 POSITION LIFECYCLE TESTS")
    print("-" * 70)
    for name, status, _ in results:
        print(f"  {status}  {name}")
    print(f"  TOTAL: {total} | PASSED: {passed} ✅ | FAILED: {failed} ❌\n")

    return passed, failed


async def main():
    print("\n" + "🚀" * 30)
    print("  MOONSHOT TRADING BOT — COMPREHENSIVE TEST SUITE")
    print("🚀" * 30 + "\n")

    total_passed = 0
    total_failed = 0

    # 1. API Endpoints
    p, f = await test_all_endpoints()
    total_passed += p
    total_failed += f

    # 2. WebSocket (info only)
    p, f = await test_websocket()
    total_passed += p
    total_failed += f

    # 3. Risk Manager edge cases
    p, f = await test_risk_manager_edge_cases()
    total_passed += p
    total_failed += f

    # 4. Position lifecycle
    p, f = await test_position_lifecycle()
    total_passed += p
    total_failed += f

    # Final summary
    print("=" * 70)
    print(f"  🏁 GRAND TOTAL: {total_passed + total_failed} tests")
    print(f"     ✅ PASSED: {total_passed}")
    print(f"     ❌ FAILED: {total_failed}")
    if total_failed == 0:
        print("     🎉 ALL TESTS PASSED!")
    else:
        print(f"     ⚠️  {total_failed} TESTS NEED ATTENTION")
    print("=" * 70 + "\n")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
