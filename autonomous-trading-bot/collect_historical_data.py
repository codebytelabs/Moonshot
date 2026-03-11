#!/usr/bin/env python3
"""
Historical Data Collection Script for Backtesting Framework.

Collects OHLCV data for 50+ cryptocurrency pairs with 24h volume >$2M
across multiple timeframes (5m, 15m, 1h, 4h, 1d) from January 2021 to December 2024.

Usage:
    python collect_historical_data.py [--symbols-file SYMBOLS_FILE] [--max-concurrent N]
"""
import asyncio
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.exchange_ccxt import ExchangeConnector
from src.historical_data_collector import HistoricalDataCollector
from src.config import get_settings


# Default symbols with high volume (>$2M 24h volume)
DEFAULT_SYMBOLS = [
    # Major pairs
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT",
    "SOL/USDT", "DOGE/USDT", "DOT/USDT", "MATIC/USDT", "AVAX/USDT",
    
    # DeFi tokens
    "UNI/USDT", "LINK/USDT", "AAVE/USDT", "CRV/USDT", "SUSHI/USDT",
    "COMP/USDT", "MKR/USDT", "SNX/USDT", "YFI/USDT", "1INCH/USDT",
    
    # Layer 1/2
    "ATOM/USDT", "NEAR/USDT", "FTM/USDT", "ALGO/USDT", "ONE/USDT",
    "HBAR/USDT", "EGLD/USDT", "FLOW/USDT", "ICP/USDT", "FIL/USDT",
    
    # Exchange tokens
    "FTT/USDT", "CRO/USDT", "HT/USDT", "OKB/USDT", "LEO/USDT",
    
    # Meme/Gaming
    "SHIB/USDT", "SAND/USDT", "MANA/USDT", "AXS/USDT", "GALA/USDT",
    
    # Other high volume
    "LTC/USDT", "BCH/USDT", "ETC/USDT", "XLM/USDT", "TRX/USDT",
    "VET/USDT", "EOS/USDT", "XTZ/USDT", "THETA/USDT", "FIL/USDT",
    "APE/USDT", "LDO/USDT", "ARB/USDT", "OP/USDT", "IMX/USDT",
]

# Timeframes to collect
TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]

# Date range
START_DATE = datetime(2021, 1, 1)
END_DATE = datetime(2026, 2, 15)  # Updated to current date


async def verify_symbol_volume(
    exchange: ExchangeConnector,
    symbol: str,
    min_volume_usd: float = 2_000_000.0
) -> bool:
    """
    Verify that a symbol has sufficient 24h volume.
    
    Args:
        exchange: Exchange connector
        symbol: Trading pair to check
        min_volume_usd: Minimum 24h volume in USD
        
    Returns:
        True if volume is sufficient, False otherwise
    """
    try:
        ticker = await exchange.fetch_ticker(symbol)
        volume_24h = ticker.get("quoteVolume", 0)
        
        if volume_24h >= min_volume_usd:
            logger.info(f"✓ {symbol}: ${volume_24h:,.0f} 24h volume")
            return True
        else:
            logger.warning(
                f"✗ {symbol}: ${volume_24h:,.0f} 24h volume "
                f"(below ${min_volume_usd:,.0f} threshold)"
            )
            return False
    except Exception as e:
        logger.error(f"✗ {symbol}: Error checking volume - {e}")
        return False


async def filter_symbols_by_volume(
    exchange: ExchangeConnector,
    symbols: List[str],
    min_volume_usd: float = 2_000_000.0
) -> List[str]:
    """
    Filter symbols to only those with sufficient 24h volume.
    
    Args:
        exchange: Exchange connector
        symbols: List of symbols to check
        min_volume_usd: Minimum 24h volume in USD
        
    Returns:
        List of symbols meeting volume criteria
    """
    logger.info(f"Filtering {len(symbols)} symbols by 24h volume >$2M...")
    
    tasks = [verify_symbol_volume(exchange, symbol, min_volume_usd) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_symbols = []
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            logger.error(f"Error checking {symbol}: {result}")
            continue
        if result:
            valid_symbols.append(symbol)
    
    logger.info(f"Found {len(valid_symbols)} symbols with sufficient volume")
    return valid_symbols


async def collect_all_data(
    symbols: List[str],
    timeframes: List[str],
    start_date: datetime,
    end_date: datetime,
    storage_path: str = "./data/historical",
    max_concurrent: int = 5
):
    """
    Collect historical data for all symbols and timeframes.
    
    Args:
        symbols: List of trading pairs
        timeframes: List of timeframes to collect
        start_date: Start date for collection
        end_date: End date for collection
        storage_path: Directory to store Parquet files
        max_concurrent: Maximum concurrent API requests
    """
    logger.info("=" * 80)
    logger.info("HISTORICAL DATA COLLECTION")
    logger.info("=" * 80)
    logger.info(f"Symbols: {len(symbols)}")
    logger.info(f"Timeframes: {timeframes}")
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Storage: {storage_path}")
    logger.info(f"Max concurrent: {max_concurrent}")
    logger.info("=" * 80)
    
    # Initialize exchange (using public API, no credentials needed for historical data)
    settings = get_settings()
    exchange = ExchangeConnector(
        name=settings.exchange_name,
        api_key=None,  # Public API for historical data
        api_secret=None,
        sandbox=False
    )
    await exchange.initialize()
    
    # Filter symbols by volume
    valid_symbols = await filter_symbols_by_volume(exchange, symbols)
    
    if len(valid_symbols) < 50:
        logger.warning(
            f"Only {len(valid_symbols)} symbols meet volume criteria. "
            f"Target is 50+ symbols."
        )
    
    # Initialize data collector
    collector = HistoricalDataCollector(exchange, storage_path)
    
    # Collect and save all data
    logger.info("\nStarting bulk data collection...")
    results = await collector.collect_bulk_and_save(
        symbols=valid_symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        max_concurrent=max_concurrent,
        validate=True
    )
    
    # Generate summary report
    logger.info("\n" + "=" * 80)
    logger.info("COLLECTION SUMMARY")
    logger.info("=" * 80)
    
    total_datasets = 0
    successful_datasets = 0
    failed_datasets = 0
    total_quality_issues = 0
    
    for symbol, timeframe_data in results.items():
        for timeframe, (file_path, quality_report) in timeframe_data.items():
            total_datasets += 1
            
            if file_path is not None:
                successful_datasets += 1
                
                if quality_report and quality_report.has_issues():
                    total_quality_issues += 1
                    logger.warning(
                        f"{symbol} {timeframe}: Quality issues - {quality_report.to_dict()}"
                    )
            else:
                failed_datasets += 1
                logger.error(f"{symbol} {timeframe}: Collection failed")
    
    logger.info(f"\nTotal datasets: {total_datasets}")
    logger.info(f"Successful: {successful_datasets}")
    logger.info(f"Failed: {failed_datasets}")
    logger.info(f"Datasets with quality issues: {total_quality_issues}")
    logger.info(f"\nSuccess rate: {successful_datasets/total_datasets*100:.1f}%")
    
    # Close exchange
    await exchange.close()
    
    logger.info("\n" + "=" * 80)
    logger.info("COLLECTION COMPLETE")
    logger.info("=" * 80)


def load_symbols_from_file(file_path: str) -> List[str]:
    """
    Load symbols from a text file (one symbol per line).
    
    Args:
        file_path: Path to symbols file
        
    Returns:
        List of symbols
    """
    symbols = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                symbols.append(line)
    return symbols


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect historical OHLCV data for backtesting"
    )
    parser.add_argument(
        "--symbols-file",
        type=str,
        help="Path to file containing symbols (one per line)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum concurrent API requests (default: 5)"
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default="./data/historical",
        help="Directory to store Parquet files (default: ./data/historical)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2021-01-01",
        help="Start date (YYYY-MM-DD, default: 2021-01-01)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2026-02-15",
        help="End date (YYYY-MM-DD, default: 2026-02-15)"
    )
    
    args = parser.parse_args()
    
    # Load symbols
    if args.symbols_file:
        logger.info(f"Loading symbols from {args.symbols_file}")
        symbols = load_symbols_from_file(args.symbols_file)
    else:
        logger.info(f"Using default symbol list ({len(DEFAULT_SYMBOLS)} symbols)")
        symbols = DEFAULT_SYMBOLS
    
    # Parse dates
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    
    # Run collection
    await collect_all_data(
        symbols=symbols,
        timeframes=TIMEFRAMES,
        start_date=start_date,
        end_date=end_date,
        storage_path=args.storage_path,
        max_concurrent=args.max_concurrent
    )


if __name__ == "__main__":
    asyncio.run(main())
