#!/usr/bin/env python3
"""
Test script for historical data collection.
Collects a small sample to verify the system works before running full collection.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent))

from src.exchange_ccxt import ExchangeConnector
from src.historical_data_collector import HistoricalDataCollector
from src.config import get_settings


async def test_collection():
    """Test data collection with a small sample."""
    logger.info("=" * 80)
    logger.info("TESTING HISTORICAL DATA COLLECTION")
    logger.info("=" * 80)
    
    # Test parameters
    test_symbols = ["BTC/USDT", "ETH/USDT"]
    test_timeframes = ["1h", "1d"]
    test_start = datetime.now() - timedelta(days=7)  # Last 7 days
    test_end = datetime.now()
    storage_path = "./data/test_historical"
    
    logger.info(f"Test symbols: {test_symbols}")
    logger.info(f"Test timeframes: {test_timeframes}")
    logger.info(f"Test date range: {test_start.date()} to {test_end.date()}")
    logger.info(f"Storage path: {storage_path}")
    logger.info("=" * 80)
    
    # Initialize exchange
    settings = get_settings()
    exchange = ExchangeConnector(
        name=settings.exchange_name,
        api_key=None,
        api_secret=None,
        sandbox=False
    )
    await exchange.initialize()
    logger.info(f"✓ Exchange initialized: {exchange.name}")
    
    # Initialize collector
    collector = HistoricalDataCollector(exchange, storage_path)
    logger.info(f"✓ Collector initialized")
    
    # Test single symbol collection
    logger.info("\n--- Testing single symbol collection ---")
    df = await collector.collect_symbol_data(
        symbol="BTC/USDT",
        timeframe="1h",
        start_date=test_start,
        end_date=test_end
    )
    
    if not df.empty:
        logger.info(f"✓ Collected {len(df)} candles for BTC/USDT 1h")
        logger.info(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        logger.info(f"  Sample data:\n{df.head()}")
    else:
        logger.error("✗ Failed to collect data for BTC/USDT 1h")
        return False
    
    # Test data quality validation
    logger.info("\n--- Testing data quality validation ---")
    quality_report = collector.validate_data_quality(df, "1h", "BTC/USDT")
    logger.info(f"Quality report: {quality_report.to_dict()}")
    
    if quality_report.has_issues():
        logger.warning("⚠ Quality issues detected (this is normal for test data)")
    else:
        logger.info("✓ No quality issues detected")
    
    # Test Parquet save/load
    logger.info("\n--- Testing Parquet save/load ---")
    file_path = collector.save_to_parquet(df, "BTC/USDT", "1h")
    
    if file_path and file_path.exists():
        logger.info(f"✓ Saved to {file_path}")
        
        # Test loading
        loaded_df = collector.load_from_parquet("BTC/USDT", "1h")
        if loaded_df is not None and len(loaded_df) == len(df):
            logger.info(f"✓ Loaded {len(loaded_df)} candles from Parquet")
        else:
            logger.error("✗ Failed to load data from Parquet")
            return False
    else:
        logger.error("✗ Failed to save to Parquet")
        return False
    
    # Test bulk collection
    logger.info("\n--- Testing bulk collection ---")
    results = await collector.collect_bulk_and_save(
        symbols=test_symbols,
        timeframes=test_timeframes,
        start_date=test_start,
        end_date=test_end,
        max_concurrent=2,
        validate=True
    )
    
    success_count = 0
    for symbol, timeframe_data in results.items():
        for timeframe, (file_path, quality_report) in timeframe_data.items():
            if file_path is not None:
                success_count += 1
                logger.info(f"✓ {symbol} {timeframe}: Saved successfully")
            else:
                logger.error(f"✗ {symbol} {timeframe}: Failed")
    
    total_expected = len(test_symbols) * len(test_timeframes)
    logger.info(f"\nBulk collection: {success_count}/{total_expected} successful")
    
    # Close exchange
    await exchange.close()
    logger.info("\n✓ Exchange closed")
    
    # Summary
    logger.info("\n" + "=" * 80)
    if success_count == total_expected:
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 80)
        logger.info("\nYou can now run the full collection:")
        logger.info("  python collect_historical_data.py")
        return True
    else:
        logger.error("✗ SOME TESTS FAILED")
        logger.info("=" * 80)
        logger.info("\nPlease fix the issues before running full collection.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_collection())
    sys.exit(0 if success else 1)
