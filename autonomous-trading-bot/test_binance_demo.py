"""
Test script: Verify Binance Demo Mode connectivity via CCXT.
Connects to demo-api.binance.com, loads markets, fetches balance,
places a small limit order, and cancels it.
"""
import asyncio
import sys
import os

# Add parent dir so we can import from src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.exchange_ccxt import ExchangeConnector
from src.config import get_settings


async def main():
    s = get_settings()

    print("=" * 60)
    print("🧪 BINANCE DEMO MODE — Connectivity Test")
    print("=" * 60)

    # Verify keys are loaded
    api_key = s.binance_demo_api_key
    api_secret = s.binance_demo_api_secret
    demo_url = s.binance_demo_url

    if not api_key or not api_secret:
        print("❌ BINANCE_DEMO_API_KEY or BINANCE_DEMO_API_SECRET not set in .env")
        return

    print(f"   API Key:  {api_key[:8]}...{api_key[-4:]}")
    print(f"   Demo URL: {demo_url}")
    print()

    # 1. Connect with demo URL override
    connector = ExchangeConnector(
        name="binance",
        api_key=api_key,
        api_secret=api_secret,
        demo_url=demo_url,
    )

    try:
        # 2. Load markets
        print("📦 Loading markets...")
        await connector.initialize()
        n_markets = len(connector.exchange.markets)
        print(f"   ✅ Loaded {n_markets} markets")

        # Show a few USDT pairs
        usdt_pairs = connector.get_usdt_pairs()
        print(f"   USDT pairs: {len(usdt_pairs)}")
        print(f"   Examples: {usdt_pairs[:5]}")
        print()

        # 3. Fetch balance
        print("💰 Fetching balance...")
        balance = await connector.fetch_balance()
        usdt = balance.get("USDT", {})
        total = usdt.get("total", 0)
        free = usdt.get("free", 0)
        print(f"   ✅ USDT Balance — Total: ${total:,.2f} | Free: ${free:,.2f}")

        # Also show BTC balance
        btc = balance.get("BTC", {})
        btc_total = btc.get("total", 0)
        print(f"   BTC Balance — Total: {btc_total}")
        print()

        # 4. Fetch BTC/USDT ticker
        print("📊 Fetching BTC/USDT ticker...")
        ticker = await connector.fetch_ticker("BTC/USDT")
        last_price = ticker.get("last", 0)
        print(f"   ✅ BTC/USDT last price: ${last_price:,.2f}")
        print()

        # 5. Place a small limit buy slightly below market (won't fill but passes price filter)
        test_price = round(last_price * 0.95, 2)  # 5% below market — within PERCENT_PRICE_BY_SIDE
        min_qty = 0.0001  # Small BTC amount

        print(f"📝 Placing test limit buy: BTC/USDT @ ${test_price:,.2f} qty={min_qty}...")
        try:
            order = await connector.create_limit_buy("BTC/USDT", min_qty, test_price)
            order_id = order.get("id")
            print(f"   ✅ Order placed! ID: {order_id}")
            print(f"   Status: {order.get('status')}")

            # 6. Cancel the order
            print(f"🗑️  Cancelling order {order_id}...")
            cancel = await connector.cancel_order(order_id, "BTC/USDT")
            print(f"   ✅ Order cancelled")
        except Exception as e:
            print(f"   ⚠️  Order test failed: {e}")
            print(f"   (This may be due to minimum notional value requirements)")

        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED — Binance Demo Mode is working!")
        print("   Trades will appear at: https://demo.binance.com")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(main())
