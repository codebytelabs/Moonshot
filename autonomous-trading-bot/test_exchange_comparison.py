"""
Exchange Comparison Test — Gate.io Testnet vs Binance Demo Mode
Determines which exchange provides better demo trading experience.
Tests: connectivity, market loading, USDT pairs, volumes, OHLCV, balance, order placement.
"""
import asyncio
import sys
import os
import time

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ccxt.async_support as ccxt_async


# ─── Load .env ────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

# Gate.io testnet keys
GATE_API_KEY = os.getenv("GATEIO_TESTNET_API_KEY", "")
GATE_API_SECRET = os.getenv("GATEIO_TESTNET_API_SECRET", "")

# Binance demo keys
BINANCE_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_TESTNET_Secret_KEY", "")


# ─── Test functions ───────────────────────────────────────────────────────────

async def test_exchange(name: str, exchange: ccxt_async.Exchange, use_sandbox: bool = True):
    """Run comprehensive tests on an exchange instance."""
    results = {
        "name": name,
        "connected": False,
        "markets_loaded": 0,
        "usdt_pairs": 0,
        "top_volume_pairs": [],
        "ohlcv_works": False,
        "ticker_works": False,
        "balance_works": False,
        "balance_info": {},
        "order_book_works": False,
        "can_place_order": False,
        "order_result": None,
        "latency_ms": {},
        "errors": [],
    }

    try:
        # 1. Set sandbox mode
        if use_sandbox:
            exchange.set_sandbox_mode(True)
            print(f"  [{name}] Sandbox mode enabled")

        # 2. Load markets
        t0 = time.monotonic()
        await exchange.load_markets()
        elapsed_ms = (time.monotonic() - t0) * 1000
        results["connected"] = True
        results["markets_loaded"] = len(exchange.markets)
        results["latency_ms"]["load_markets"] = round(elapsed_ms, 1)
        print(f"  [{name}] ✅ Loaded {results['markets_loaded']} markets in {elapsed_ms:.0f}ms")

        # 3. Count USDT spot pairs
        usdt_pairs = []
        for symbol, market in exchange.markets.items():
            if (market.get("quote") == "USDT" and
                market.get("active", True) and
                market.get("spot", True) and
                not market.get("option", False)):
                usdt_pairs.append(symbol)
        results["usdt_pairs"] = len(usdt_pairs)
        print(f"  [{name}] ✅ Found {len(usdt_pairs)} active USDT spot pairs")

        # 4. Fetch tickers for top volume analysis
        try:
            t0 = time.monotonic()
            tickers = await exchange.fetch_tickers()
            elapsed_ms = (time.monotonic() - t0) * 1000
            results["latency_ms"]["fetch_tickers"] = round(elapsed_ms, 1)
            results["ticker_works"] = True

            # Find top volume USDT pairs
            volume_data = []
            for symbol in usdt_pairs:
                if symbol in tickers:
                    vol = tickers[symbol].get("quoteVolume", 0) or 0
                    price = tickers[symbol].get("last", 0) or 0
                    volume_data.append((symbol, vol, price))

            volume_data.sort(key=lambda x: x[1], reverse=True)
            results["top_volume_pairs"] = volume_data[:20]

            # Count pairs with >$1M volume
            high_vol = [v for v in volume_data if v[1] > 1_000_000]
            print(f"  [{name}] ✅ Tickers fetched in {elapsed_ms:.0f}ms — {len(high_vol)} pairs with >$1M volume")

            if volume_data:
                top = volume_data[0]
                print(f"  [{name}]    Top pair: {top[0]} — Vol: ${top[1]:,.0f} — Price: ${top[2]:.4f}")
        except Exception as e:
            results["errors"].append(f"fetch_tickers: {e}")
            print(f"  [{name}] ❌ fetch_tickers failed: {e}")

        # 5. Test OHLCV
        test_symbol = "BTC/USDT" if "BTC/USDT" in exchange.markets else usdt_pairs[0] if usdt_pairs else None
        if test_symbol:
            try:
                t0 = time.monotonic()
                ohlcv = await exchange.fetch_ohlcv(test_symbol, "5m", limit=50)
                elapsed_ms = (time.monotonic() - t0) * 1000
                results["latency_ms"]["fetch_ohlcv"] = round(elapsed_ms, 1)
                results["ohlcv_works"] = True
                print(f"  [{name}] ✅ OHLCV ({test_symbol}, 5m): {len(ohlcv)} candles in {elapsed_ms:.0f}ms")
            except Exception as e:
                results["errors"].append(f"fetch_ohlcv: {e}")
                print(f"  [{name}] ❌ fetch_ohlcv failed: {e}")

        # 6. Test Order Book
        if test_symbol:
            try:
                t0 = time.monotonic()
                ob = await exchange.fetch_order_book(test_symbol, limit=10)
                elapsed_ms = (time.monotonic() - t0) * 1000
                results["latency_ms"]["order_book"] = round(elapsed_ms, 1)
                results["order_book_works"] = True
                bids = len(ob.get("bids", []))
                asks = len(ob.get("asks", []))
                spread = 0
                if ob.get("bids") and ob.get("asks"):
                    spread = ob["asks"][0][0] - ob["bids"][0][0]
                print(f"  [{name}] ✅ Order book ({test_symbol}): {bids} bids, {asks} asks, spread=${spread:.2f}")
            except Exception as e:
                results["errors"].append(f"order_book: {e}")
                print(f"  [{name}] ❌ order_book failed: {e}")

        # 7. Test Balance
        try:
            t0 = time.monotonic()
            balance = await exchange.fetch_balance()
            elapsed_ms = (time.monotonic() - t0) * 1000
            results["latency_ms"]["fetch_balance"] = round(elapsed_ms, 1)
            results["balance_works"] = True

            # Show relevant balances
            usdt_bal = balance.get("USDT", {})
            btc_bal = balance.get("BTC", {})
            results["balance_info"] = {
                "USDT_free": usdt_bal.get("free", 0),
                "USDT_total": usdt_bal.get("total", 0),
                "BTC_free": btc_bal.get("free", 0),
                "BTC_total": btc_bal.get("total", 0),
            }
            print(f"  [{name}] ✅ Balance — USDT: ${usdt_bal.get('free', 0):,.2f} free / ${usdt_bal.get('total', 0):,.2f} total")
            print(f"  [{name}]            BTC: {btc_bal.get('free', 0):.8f} free / {btc_bal.get('total', 0):.8f} total")
        except Exception as e:
            results["errors"].append(f"fetch_balance: {e}")
            print(f"  [{name}] ❌ fetch_balance failed: {e}")

        # 8. Test Order Placement (small limit buy far below market — cancel immediately)
        if test_symbol and results["balance_works"]:
            try:
                ticker = await exchange.fetch_ticker(test_symbol)
                last_price = ticker.get("last", 0)
                if last_price > 0:
                    # Place limit buy at 50% below market (should not fill)
                    test_price = round(last_price * 0.5, 2)
                    # Minimum amount
                    market_info = exchange.markets.get(test_symbol, {})
                    min_amount = market_info.get("limits", {}).get("amount", {}).get("min", 0.001)
                    test_amount = max(min_amount, 0.0001)

                    t0 = time.monotonic()
                    order = await exchange.create_order(test_symbol, "limit", "buy", test_amount, test_price)
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    results["latency_ms"]["create_order"] = round(elapsed_ms, 1)
                    results["can_place_order"] = True
                    results["order_result"] = {
                        "id": order.get("id"),
                        "status": order.get("status"),
                        "symbol": test_symbol,
                        "amount": test_amount,
                        "price": test_price,
                    }
                    print(f"  [{name}] ✅ Limit order placed: {test_symbol} buy {test_amount} @ ${test_price} — ID={order.get('id')}")

                    # Cancel it
                    try:
                        await exchange.cancel_order(order["id"], test_symbol)
                        print(f"  [{name}] ✅ Order cancelled successfully")
                    except Exception as ce:
                        print(f"  [{name}] ⚠️  Cancel failed (may have been auto-rejected): {ce}")
            except Exception as e:
                results["errors"].append(f"create_order: {e}")
                print(f"  [{name}] ❌ Order placement failed: {e}")

    except Exception as e:
        results["errors"].append(f"connection: {e}")
        print(f"  [{name}] ❌ Connection/initialization failed: {e}")

    finally:
        try:
            await exchange.close()
        except:
            pass

    return results


async def main():
    print("=" * 70)
    print("  🔬 EXCHANGE COMPARISON: Gate.io Testnet vs Binance Demo")
    print("=" * 70)

    # Gate.io Testnet
    print(f"\n{'─' * 50}")
    print(f"  📊 Testing GATE.IO TESTNET")
    print(f"{'─' * 50}")
    gate_exchange = ccxt_async.gateio({
        "apiKey": GATE_API_KEY,
        "secret": GATE_API_SECRET,
        "enableRateLimit": True,
        "timeout": 30000,
    })
    gate_results = await test_exchange("Gate.io Testnet", gate_exchange, use_sandbox=True)

    # Binance Demo
    print(f"\n{'─' * 50}")
    print(f"  📊 Testing BINANCE DEMO MODE")
    print(f"{'─' * 50}")
    binance_exchange = ccxt_async.binance({
        "apiKey": BINANCE_API_KEY,
        "secret": BINANCE_API_SECRET,
        "enableRateLimit": True,
        "timeout": 30000,
    })
    binance_results = await test_exchange("Binance Demo", binance_exchange, use_sandbox=True)

    # ─── Comparison Report ────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  📋 COMPARISON REPORT")
    print(f"{'=' * 70}")

    headers = ["Metric", "Gate.io Testnet", "Binance Demo"]
    rows = [
        ("Connected", gate_results["connected"], binance_results["connected"]),
        ("Markets Loaded", gate_results["markets_loaded"], binance_results["markets_loaded"]),
        ("Active USDT Pairs", gate_results["usdt_pairs"], binance_results["usdt_pairs"]),
        ("Tickers Work", gate_results["ticker_works"], binance_results["ticker_works"]),
        ("OHLCV Work", gate_results["ohlcv_works"], binance_results["ohlcv_works"]),
        ("Order Book Work", gate_results["order_book_works"], binance_results["order_book_works"]),
        ("Balance Work", gate_results["balance_works"], binance_results["balance_works"]),
        ("Order Placement", gate_results["can_place_order"], binance_results["can_place_order"]),
    ]

    print(f"\n  {'Metric':<25} {'Gate.io':>20} {'Binance':>20}")
    print(f"  {'─' * 65}")
    for label, g, b in rows:
        g_str = "✅" if g is True else (str(g) if not isinstance(g, bool) else "❌")
        b_str = "✅" if b is True else (str(b) if not isinstance(b, bool) else "❌")
        print(f"  {label:<25} {g_str:>20} {b_str:>20}")

    # Volume comparison
    print(f"\n  {'Top Volume USDT Pairs':}")
    print(f"  {'─' * 65}")
    gate_top = gate_results.get("top_volume_pairs", [])[:5]
    binance_top = binance_results.get("top_volume_pairs", [])[:5]

    if gate_top:
        print(f"  Gate.io (top 5):")
        for sym, vol, price in gate_top:
            print(f"    {sym:<20} Vol: ${vol:>15,.0f}  Price: ${price:.4f}")
    if binance_top:
        print(f"  Binance (top 5):")
        for sym, vol, price in binance_top:
            print(f"    {sym:<20} Vol: ${vol:>15,.0f}  Price: ${price:.4f}")

    # Balance comparison
    print(f"\n  {'Demo Account Balances':}")
    print(f"  {'─' * 65}")
    for name, res in [("Gate.io", gate_results), ("Binance", binance_results)]:
        bi = res.get("balance_info", {})
        print(f"  {name}: USDT=${bi.get('USDT_free', 0):,.2f} | BTC={bi.get('BTC_free', 0):.8f}")

    # Latency comparison
    print(f"\n  {'Latency (ms)':}")
    print(f"  {'─' * 65}")
    all_endpoints = set(gate_results.get("latency_ms", {}).keys()) | set(binance_results.get("latency_ms", {}).keys())
    for ep in sorted(all_endpoints):
        g_lat = gate_results.get("latency_ms", {}).get(ep, "N/A")
        b_lat = binance_results.get("latency_ms", {}).get(ep, "N/A")
        print(f"  {ep:<25} {str(g_lat):>20} {str(b_lat):>20}")

    # Errors
    print(f"\n  {'Errors':}")
    print(f"  {'─' * 65}")
    for name, res in [("Gate.io", gate_results), ("Binance", binance_results)]:
        if res["errors"]:
            for e in res["errors"]:
                print(f"  ❌ [{name}] {e}")
        else:
            print(f"  ✅ [{name}] No errors")

    # ─── Scoring ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  🏆 SCORING")
    print(f"{'=' * 70}")

    gate_score = 0
    binance_score = 0

    # Connected (must-have)
    if gate_results["connected"]: gate_score += 10
    if binance_results["connected"]: binance_score += 10

    # Markets count
    if gate_results["markets_loaded"] > binance_results["markets_loaded"]:
        gate_score += 5
    elif binance_results["markets_loaded"] > gate_results["markets_loaded"]:
        binance_score += 5

    # USDT pairs (important for our bot)
    if gate_results["usdt_pairs"] > binance_results["usdt_pairs"]:
        gate_score += 10
    elif binance_results["usdt_pairs"] > gate_results["usdt_pairs"]:
        binance_score += 10

    # Volume (the more realistic, the better)
    gate_total_vol = sum(v[1] for v in gate_results.get("top_volume_pairs", []))
    binance_total_vol = sum(v[1] for v in binance_results.get("top_volume_pairs", []))
    if gate_total_vol > binance_total_vol:
        gate_score += 15
    elif binance_total_vol > gate_total_vol:
        binance_score += 15

    # Feature completeness
    for key in ["ticker_works", "ohlcv_works", "balance_works", "order_book_works", "can_place_order"]:
        if gate_results.get(key): gate_score += 5
        if binance_results.get(key): binance_score += 5

    # Balance (need demo funds to trade)
    gate_usdt = gate_results.get("balance_info", {}).get("USDT_free", 0) or 0
    binance_usdt = binance_results.get("balance_info", {}).get("USDT_free", 0) or 0
    if gate_usdt > 0: gate_score += 10
    if binance_usdt > 0: binance_score += 10

    # Fewer errors = better
    if len(gate_results["errors"]) < len(binance_results["errors"]):
        gate_score += 5
    elif len(binance_results["errors"]) < len(gate_results["errors"]):
        binance_score += 5

    print(f"\n  Gate.io Testnet:  {gate_score}/80 points")
    print(f"  Binance Demo:    {binance_score}/80 points")

    if gate_score > binance_score:
        winner = "gateio"
        print(f"\n  🏆 WINNER: Gate.io Testnet (+{gate_score - binance_score} points)")
    elif binance_score > gate_score:
        winner = "binance"
        print(f"\n  🏆 WINNER: Binance Demo (+{binance_score - gate_score} points)")
    else:
        winner = "binance"  # Default to binance if tie (more realistic data)
        print(f"\n  🏆 TIE — Defaulting to Binance (more realistic market data)")

    print(f"\n  RECOMMENDATION: Use **{winner}** for demo trading")
    print(f"{'=' * 70}")

    return gate_results, binance_results, winner


if __name__ == "__main__":
    gate_res, binance_res, winner = asyncio.run(main())
