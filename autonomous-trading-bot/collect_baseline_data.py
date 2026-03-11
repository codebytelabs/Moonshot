"""
Collect minimal historical data for baseline backtest (Task 3.14).

Collects data for 5 symbols, 2 timeframes, 2021-2024.
This is a subset for quick baseline testing.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.historical_data_collector import HistoricalDataCollector
from src.exchange_ccxt import ExchangeConnector


async def collect_baseline_data():
    """Collect minimal data for baseline backtest."""
    logger.info("=" * 80)
    logger.info("COLLECTING BASELINE DATA FOR TASK 3.14")
    logger.info("=" * 80)
    
    # Configuration
    # Using 2023-2024 for baseline (2 years instead of 4) to make collection feasible
    # This still covers bull and bear market conditions
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 12, 31)
    
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "XRP/USDT"
    ]
    
    timeframes = ["5m", "1h"]
    
    # Configuration
    # Using 2023-2024 for baseline (2 years instead of 4) to make collection feasible
    # This still covers bull and bear market conditions
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 12, 31)
    
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Timeframes: {timeframes}")
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Total datasets: {len(symbols)} × {len(timeframes)} = {len(symbols) * len(timeframes)}")
    
    # Initialize
    exchange = ExchangeConnector(name="binance", sandbox=False)
    await exchange.initialize()  # Load markets
    
    collector = HistoricalDataCollector(
        exchange=exchange,
        storage_path="./data/historical"
    )
    
    # Collect data
    logger.info("Starting data collection...")
    logger.info("This will take approximately 30-60 minutes...")
    
    results = await collector.collect_bulk_and_save(
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        max_concurrent=3,  # Conservative to avoid rate limits
        validate=True
    )
    
    # Summary
    logger.info("=" * 80)
    logger.info("COLLECTION SUMMARY")
    logger.info("=" * 80)
    
    total_datasets = 0
    successful = 0
    failed = 0
    
    for symbol, timeframe_results in results.items():
        for timeframe, (file_path, quality_report) in timeframe_results.items():
            total_datasets += 1
            if file_path:
                successful += 1
                logger.info(f"✓ {symbol} {timeframe}: {file_path}")
                if quality_report:
                    qr = quality_report.to_dict()
                    logger.info(
                        f"  Quality: {qr['completeness_pct']:.1f}% complete, "
                        f"{qr['missing_gaps']} gaps, "
                        f"{qr['zero_volume_count']} zero volume bars"
                    )
            else:
                failed += 1
                logger.error(f"✗ {symbol} {timeframe}: FAILED")
    
    logger.info("-" * 80)
    logger.info(f"Total: {total_datasets} datasets")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success rate: {(successful/total_datasets)*100:.1f}%")
    logger.info("=" * 80)
    
    if successful >= len(symbols) * len(timeframes) * 0.8:  # 80% success threshold
        logger.info("✓ Data collection successful! Ready for baseline backtest.")
        return True
    else:
        logger.error("✗ Data collection incomplete. Some datasets failed.")
        return False


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Add file logging
    log_file = Path("./logs") / f"baseline_data_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file.parent.mkdir(exist_ok=True)
    logger.add(log_file, level="DEBUG")
    
    # Run collection
    try:
        success = asyncio.run(collect_baseline_data())
        if success:
            logger.info("Data collection completed successfully!")
            logger.info("You can now run: python run_baseline_backtest.py")
            sys.exit(0)
        else:
            logger.error("Data collection failed!")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Data collection error: {e}")
        sys.exit(1)
