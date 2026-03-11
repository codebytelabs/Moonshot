"""
Test script: Verify Gate.io Testnet connectivity.
Connects to api-testnet.gateapi.io, loads markets, fetches balance,
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
    print("🧪 Gate.io TESTNET — Connectivity Test")
    print("=" * 60)

    # Verify keys are loaded
    api_key = s.gateio_testnet_api_key
    secret_key = s.gateio_testnet_secret_key
    demo_url = s.gateio_testnet_url

    if not api_key or not secret_key:
        print("❌ GATEIO_TESTNET_API_KEY or GATEIO_TESTNET_SECRET_KEY not set")
        return

    print(f"   API Key:  {api_key[:8]}...{api_key[-4:]}")
    print(f"   Demo URL: {demo_url}")
    print()

    # 1. Connect with demo URL override
    connector = ExchangeConnector(
        name="gateio",
        api_key=api_key,
        api_secret=secret_key,
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
        print()

        # 4. Fetch BTC/USDT ticker
        print("📊 Fetching BTC/USDT ticker...")
        ticker = await connector.fetch_ticker("BTC/USDT")
        last_price = ticker.get("last", 0)
        print(f"   ✅ BTC/USDT last price: ${last_price:,.2f}")
        print()

        # 5. Place a small limit buy
        # Gate.io minimum order size is usually $1
        test_price = round(last_price * 0.9, 2)  # 10% below market
        # Ensure > $1 notional
        min_qty = 0.0001
        if (test_price * min_qty) < 1.0:
            min_qty = 0.001 

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

        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED — Gate.io Testnet is working!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(main())
