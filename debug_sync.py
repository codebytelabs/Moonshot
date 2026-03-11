
import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_key = os.getenv("GATEIO_TESTNET_API_KEY")
    secret = os.getenv("GATEIO_TESTNET_SECRET_KEY")
    
    print(f"Connecting to Gate.io Demo with key: {api_key[:5]}...")
    
    exchange = ccxt.gateio({
        'apiKey': api_key,
        'secret': secret,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)
    
    try:
        print("Fetching balance...")
        balance = await exchange.fetch_balance()
        held = {k: v for k, v in balance['total'].items() if v > 0}
        print(f"Held assets: {held}")
        
        for asset in held:
            if asset == 'USDT': continue
            symbol = f"{asset}/USDT"
            print(f"Fetching trades for {symbol}...")
            try:
                trades = await exchange.fetch_my_trades(symbol)
                print(f"Found {len(trades)} trades for {symbol}")
                if trades:
                    print(f"Sample: {trades[0]}")
            except Exception as e:
                print(f"Error fetching trades for {symbol}: {e}")
                
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
