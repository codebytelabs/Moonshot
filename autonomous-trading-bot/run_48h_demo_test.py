"""
48-Hour Demo Trading Test Script.
Runs the bot in Gate.io testnet mode for 48 hours and generates a validation report.
"""
import asyncio
import time
from datetime import datetime, timedelta
from loguru import logger
from src.main import TradingBot
from src.config import get_settings
from src.supabase_client import SupabaseStore


async def run_48hour_demo_test():
    """
    Run 48-hour demo trading test on Gate.io testnet.
    
    Monitors:
    - Total trades executed
    - Win rate
    - Average R-multiple
    - Largest win/loss
    - Any errors or edge cases
    """
    settings = get_settings()
    
    # Verify we're in demo mode
    if settings.exchange_mode != "demo":
        logger.error("ERROR: EXCHANGE_MODE must be 'demo' for this test")
        logger.error("Please set EXCHANGE_MODE=demo in .env file")
        return
    
    if settings.exchange_name != "gateio":
        logger.error("ERROR: EXCHANGE_NAME must be 'gateio' for this test")
        logger.error("Please set EXCHANGE_NAME=gateio in .env file")
        return
    
    logger.info("=" * 80)
    logger.info("🧪 48-HOUR DEMO TRADING TEST")
    logger.info("=" * 80)
    logger.info(f"Exchange: Gate.io Testnet")
    logger.info(f"Mode: {settings.exchange_mode}")
    logger.info(f"Start Time: {datetime.now()}")
    logger.info(f"End Time: {datetime.now() + timedelta(hours=48)}")
    logger.info("=" * 80)
    
    # Initialize bot
    bot = TradingBot()
    
    try:
        # Start bot
        await bot.start()
        
        # Record start time
        start_time = time.time()
        end_time = start_time + (48 * 3600)  # 48 hours in seconds
        
        # Run trading loop for 48 hours
        logger.info("🚀 Starting 48-hour demo trading...")
        
        while time.time() < end_time:
            try:
                # Run one trading cycle
                await bot.run_cycle()
                
                # Calculate remaining time
                remaining_hours = (end_time - time.time()) / 3600
                logger.info(f"⏱️  Remaining: {remaining_hours:.1f} hours")
                
                # Sleep until next cycle
                await asyncio.sleep(settings.cycle_interval_seconds)
                
            except KeyboardInterrupt:
                logger.warning("⚠️  Test interrupted by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in trading cycle: {e}")
                # Continue running despite errors
                await asyncio.sleep(60)  # Wait 1 minute before retrying
        
        logger.info("✅ 48-hour demo test completed!")
        
        # Generate report
        await generate_48hour_report(bot.store, start_time, end_time)
        
    except Exception as e:
        logger.error(f"❌ Fatal error during demo test: {e}")
        raise
    finally:
        # Cleanup
        if bot.exchange:
            await bot.exchange.close()
        if bot.redis:
            await bot.redis.close()
        logger.info("🛑 Bot shutdown complete")


async def generate_48hour_report(store: SupabaseStore, start_time: float, end_time: float):
    """
    Generate 48-hour demo test report.
    
    Args:
        store: Supabase store instance
        start_time: Test start timestamp
        end_time: Test end timestamp
    """
    logger.info("=" * 80)
    logger.info("📊 48-HOUR DEMO TEST REPORT")
    logger.info("=" * 80)
    
    try:
        # Convert timestamps to datetime
        start_dt = datetime.fromtimestamp(start_time)
        end_dt = datetime.fromtimestamp(end_time)
        
        # Query trades from database
        trades_result = store.client.table("trades").select("*").gte(
            "timestamp", start_dt.isoformat()
        ).lte(
            "timestamp", end_dt.isoformat()
        ).execute()
        
        trades = trades_result.data if trades_result.data else []
        
        # Calculate metrics
        total_trades = len(trades)
        
        if total_trades == 0:
            logger.warning("⚠️  No trades executed during test period")
            logger.info("=" * 80)
            return
        
        # Win rate
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
        
        # R-multiples
        r_multiples = [t.get('r_multiple', 0) for t in trades if t.get('r_multiple') is not None]
        avg_r_multiple = sum(r_multiples) / len(r_multiples) if r_multiples else 0
        
        # PnL
        pnls = [t.get('pnl', 0) for t in trades if t.get('pnl') is not None]
        total_pnl = sum(pnls)
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0
        
        # Print report
        logger.info(f"Test Duration: {(end_time - start_time) / 3600:.1f} hours")
        logger.info(f"Total Trades: {total_trades}")
        logger.info(f"Winning Trades: {len(winning_trades)}")
        logger.info(f"Win Rate: {win_rate:.2f}%")
        logger.info(f"Average R-Multiple: {avg_r_multiple:.2f}R")
        logger.info(f"Total PnL: ${total_pnl:.2f}")
        logger.info(f"Largest Win: ${largest_win:.2f}")
        logger.info(f"Largest Loss: ${largest_loss:.2f}")
        
        # Validation checks
        logger.info("")
        logger.info("Validation Checks:")
        
        if total_trades >= 5:
            logger.info("✅ Minimum 5 trades executed")
        else:
            logger.warning(f"⚠️  Only {total_trades} trades executed (target: 5+)")
        
        if win_rate > 0:
            logger.info(f"✅ Win rate calculated: {win_rate:.2f}%")
        else:
            logger.warning("⚠️  No winning trades")
        
        if avg_r_multiple != 0:
            logger.info(f"✅ R-multiple tracking working: {avg_r_multiple:.2f}R")
        else:
            logger.warning("⚠️  R-multiple data missing")
        
        logger.info("=" * 80)
        
        # Save report to database
        report_data = {
            "test_type": "48hour_demo",
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_r_multiple": avg_r_multiple,
            "total_pnl": total_pnl,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "timestamp": datetime.now().isoformat()
        }
        
        store.client.table("performance_metrics").insert({
            "date": datetime.now().date().isoformat(),
            "total_trades": total_trades,
            "win_rate": win_rate / 100,
            "total_pnl": total_pnl,
            "avg_r_multiple": avg_r_multiple
        }).execute()
        
        logger.info("✅ Report saved to database")
        
    except Exception as e:
        logger.error(f"❌ Error generating report: {e}")


if __name__ == "__main__":
    asyncio.run(run_48hour_demo_test())
