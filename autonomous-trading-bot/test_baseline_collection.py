"""
Quick test to verify data collection works before running full baseline.
Collects just 7 days of data for 1 symbol.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.historical_data_collector import HistoricalDataCollector
from src.exchange_ccxt import ExchangeConnector


async def test_collection():
    """Test data collection with minimal data."""
    logger.info("Testing data collection...")
    
    # Minimal test: 1 symbol, 2 timeframes, 7 days
    symbols = ["BTC/USDT"]
    timeframes = ["5m", "1h"]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    logger.info(f"Test: {symbols} {timeframes} {start_date.date()} to {end_date.date()}")
    
    # Initialize
    exchange = ExchangeConnector(name="binance", sandbox=False)
    await exchange.initialize()
    
    collector = HistoricalDataCollector(
        exchange=exchange,
        storage_path="./data/test_baseline"
    )
    
    # Collect
    logger.info("Collecting test data...")
    results = await collector.collect_bulk_and_save(
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        max_concurrent=2,
        validate=True
    )
    
    # Check results
    success = True
    for symbol, tf_results in results.items():
        for tf, (path, quality) in tf_results.items():
            if path:
                logger.info(f"✓ {symbol} {tf}: SUCCESS")
                if quality:
                    logger.info(f"  Quality: {quality.to_dict()}")
            else:
                logger.error(f"✗ {symbol} {tf}: FAILED")
                success = False
    
    await exchange.close()
    
    if success:
        logger.info("✓ Test passed! Data collection is working.")
        logger.info("You can now run: python collect_baseline_data.py")
        return True
    else:
        logger.error("✗ Test failed!")
        return False


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    try:
        success = asyncio.run(test_collection())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception(f"Test error: {e}")
        sys.exit(1)
