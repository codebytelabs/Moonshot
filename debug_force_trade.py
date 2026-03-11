
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import ccxt.async_support as ccxt

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent
print(f"Project Root: {PROJECT_ROOT}")
sys.path.append(str(PROJECT_ROOT / "autonomous-trading-bot" / "src"))

# Load env
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("GATEIO_TESTNET_API_KEY")
SECRET_KEY = os.getenv("GATEIO_TESTNET_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    print("❌ Error: Missing Gate.io Testnet keys in .env")
    sys.exit(1)

async def force_trade():
    print("🚀 Initializing Gate.io Testnet connection...")
    exchange = ccxt.gateio({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot', 
        }
    })
    
    # 1. Important: Set Sandbox Mode
    exchange.set_sandbox_mode(True)

    try:
        # 2. Check Balance
        print("🔍 Checking Balance...")
        balance = await exchange.fetch_balance()
        usdt_free = balance['USDT']['free']
        print(f"💰 USDT Free: {usdt_free}")

        if usdt_free < 10:
            print("❌ Error: Insufficient USDT balance for test trade (< 10 USDT)")
            return

        # 3. Place Limit Order (Way below price to avoid fill, just to test placement)
        symbol = "BTC/USDT"
        
        # Get ticker to ensure we aren't buying at market top if we wanted to
        ticker = await exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"ℹ️ {symbol} Price: {current_price}")
        
        # Determine strict test price (e.g. 50% of current price to safely sit in orderbook)
        # OR better: buy a tiny amount at current price to SEE it fill if user wants "magic"
        # Since this is TESTNET, let's try to get a fill for visibility.
        # But purely for permission check, a limit order far away is safer.
        # User complained "I dont see any openorders", so let's place one that STAYS open.
        
        target_price = int(current_price * 0.8) # 20% below market
        quantity = 0.001 # Min size check? usually ~5-10 USDT. 0.001 * 50000 = $50. Safe.
        
        print(f"📝 Placing LIMIT BUY for {quantity} {symbol} @ {target_price}...")
        
        order = await exchange.create_order(
            symbol=symbol,
            type='limit',
            side='buy',
            amount=quantity,
            price=target_price
        )
        
        print("✅ Order Placed Successfully!")
        print(f"🆔 Order ID: {order['id']}")
        print(f"📋 Status: {order['status']}")
        
        # 4. Fetch Open Orders to confirm visibility
        print("🔍 Verifying Open Orders...")
        open_orders = await exchange.fetch_open_orders(symbol)
        my_order = next((o for o in open_orders if o['id'] == order['id']), None)
        
        if my_order:
             print(f"👀 FOUND in Open Orders! ID: {my_order['id']}, Price: {my_order['price']}")
        else:
             print("⚠️ WARNING: Order placed but not found in open orders immediately.")
             
        # 5. Cancel it (cleanup)
        # print(f"🗑️ Cancelling Order {order['id']}...")
        # await exchange.cancel_order(order['id'], symbol)
        # print("✅ Order Cancelled.")
        print("ℹ️ Order left OPEN for user verification on gate.io testnet website.")

    except Exception as e:
        print(f"❌ FAILED: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(force_trade())
