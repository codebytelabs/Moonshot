"""
Standalone API server for testing with REAL bot components (Demo/Live).
Initializes the TradingBot and its connections (Exchange, Redis, Supabase, AI Agents)
so the frontend can see actual data, but DOES NOT run the autonomous trading loop.
Uses direct uvicorn.Server execution for better control.
"""
import sys
import os
import asyncio
import uvicorn
from loguru import logger

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from src.main import TradingBot
from src.api import create_app

# Global bot instance
bot = TradingBot()

# Helper to initialize bot components
async def init_bot_components():
    logger.info("🚀 API Server Starting — Initializing Bot Components...")
    try:
        s = bot.settings
        
        # 1. Redis
        from src.redis_client import RedisClient
        bot.redis = RedisClient(s.redis_url, s.redis_password)
        await bot.redis.connect()
        
        # 2. Supabase
        from src.supabase_client import SupabaseStore
        bot.store = SupabaseStore(s.supabase_url, s.supabase_anon_key)
        
        # 3. Exchange
        from src.exchange_ccxt import ExchangeConnector
        
        demo_url = None
        exchange_name = s.exchange_name
        api_key = ""
        api_secret = ""

        if s.exchange_mode == "demo":
            s.mode = "demo"
            if s.exchange_name == "binance":
                api_key = s.binance_demo_api_key
                api_secret = s.binance_demo_api_secret
                demo_url = s.binance_demo_url
            elif s.exchange_name == "gateio":
                api_key = s.gateio_testnet_api_key
                api_secret = s.gateio_testnet_secret_key
                demo_url = s.gateio_testnet_url
        else:
            api_key = s.gateio_api_key if s.exchange_name == "gateio" else s.binance_api_key
            api_secret = s.gateio_api_secret if s.exchange_name == "gateio" else s.binance_api_secret

        bot.exchange = ExchangeConnector(
            name=exchange_name,
            api_key=api_key,
            api_secret=api_secret,
            sandbox=(s.mode == "paper"),
            demo_url=demo_url,
        )
        await bot.exchange.initialize()
        
        # 4. OpenRouter
        from src.openrouter_client import OpenRouterClient
        bot.openrouter = OpenRouterClient(
            api_key=s.openrouter_api_key,
            base_url=s.openrouter_base_url,
            primary_model=s.openrouter_primary_model,
            secondary_model=s.openrouter_secondary_model,
        )
        
        # 5. Position Manager
        from src.position_manager import PositionManager
        bot.pm = PositionManager(
            exchange=bot.exchange,
            settings=s,
            store=bot.store,
            paper_mode=(s.mode == "paper")
        )
        
        # 6. Risk Manager (Needed for BigBrother)
        from src.risk_manager import RiskManager
        bot.risk = RiskManager(s)
        
        # 7. Bayesian Engine (Needed for BigBrother)
        from src.bayesian_engine import BayesianDecisionEngine
        bot.engine = BayesianDecisionEngine()
        
        # 8. BigBrother
        from src.bigbrother import BigBrotherAgent
        bot.bigbrother = BigBrotherAgent(
            risk_manager=bot.risk,
            decision_engine=bot.engine,
            store=bot.store,
            openrouter_client=bot.openrouter
        )

        # 9. Sync Equity
        try:
            logger.info("💰 Fetching initial balance from exchange...")
            balance = await bot.exchange.fetch_balance()
            # Gate.io structure usually has 'total' dict
            equity = balance.get("total", {}).get("USDT", 0.0)
            
            if equity > 0:
                bot.risk.update_equity(equity)
                logger.info(f"✅ Synced equity from exchange: ${equity:.2f}")
            else:
                logger.warning(f"⚠️ Exchange returned 0 USDT equity (or missing 'total' key). Keeping default ${s.initial_equity_usd}")
                logger.debug(f"Balance dump: {balance}")
        except Exception as e:
            logger.error(f"⚠️ Failed to fetch balance: {e}")

        logger.info("✅ Bot Components Initialized! Serving live data.")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize bot components: {e}")
        import traceback
        traceback.print_exc()
        raise e

async def main():
    await init_bot_components()
    
    # Create the state dict populated with initialized components
    bot_state = {
        "mode": bot.settings.exchange_mode,
        "settings": bot.settings,
        "redis": bot.redis,
        "store": bot.store,
        "exchange": bot.exchange,
        "openrouter": bot.openrouter,
        "position_manager": bot.pm,
        "bigbrother": bot.bigbrother,
        "risk_manager": bot.risk,
        "engine": bot.engine,
    }

    app = create_app(bot_state)
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    logger.info("🚀 Starting Uvicorn Server...")
    await server.serve()

    # Cleanup after server exit
    logger.info("🛑 Shutting down components...")
    if bot.redis: await bot.redis.close()
    if bot.exchange: await bot.exchange.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}")
