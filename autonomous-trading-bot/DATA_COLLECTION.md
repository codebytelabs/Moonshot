# Historical Data Collection Guide

This guide explains how to collect historical OHLCV data for the backtesting framework.

## Overview

The `collect_historical_data.py` script collects historical market data for 50+ cryptocurrency pairs with 24h volume >$2M across multiple timeframes from January 2021 to December 2024.

**Requirements (from spec):**
- **Symbols**: 50+ cryptocurrency pairs with 24h volume >$2M
- **Timeframes**: 5m, 15m, 1h, 4h, 1d
- **Date Range**: January 2021 to February 2026 (current)
- **Storage Format**: Parquet with Snappy compression
- **Organization**: `{storage_path}/{symbol}/{timeframe}/data.parquet`

## Quick Start

### Basic Usage

```bash
cd autonomous-trading-bot
python collect_historical_data.py
```

This will:
1. Filter symbols by 24h volume (>$2M)
2. Collect data for all timeframes (5m, 15m, 1h, 4h, 1d)
3. Store data in `./data/historical/` directory
4. Validate data quality (gaps, anomalies, zero volume bars)
5. Generate a summary report

### Custom Options

```bash
# Use custom symbols file
python collect_historical_data.py --symbols-file my_symbols.txt

# Adjust concurrent requests (default: 5)
python collect_historical_data.py --max-concurrent 10

# Custom storage path
python collect_historical_data.py --storage-path /path/to/data

# Custom date range
python collect_historical_data.py --start-date 2022-01-01 --end-date 2023-12-31
```

## Default Symbols

The script includes 55 default symbols across various categories:

- **Major pairs**: BTC/USDT, ETH/USDT, BNB/USDT, XRP/USDT, ADA/USDT, SOL/USDT, etc.
- **DeFi tokens**: UNI/USDT, LINK/USDT, AAVE/USDT, CRV/USDT, etc.
- **Layer 1/2**: ATOM/USDT, NEAR/USDT, FTM/USDT, ALGO/USDT, etc.
- **Exchange tokens**: FTT/USDT, CRO/USDT, HT/USDT, OKB/USDT, etc.
- **Meme/Gaming**: SHIB/USDT, SAND/USDT, MANA/USDT, AXS/USDT, etc.

## Custom Symbols File

Create a text file with one symbol per line:

```
# my_symbols.txt
BTC/USDT
ETH/USDT
SOL/USDT
# Comments are supported
AVAX/USDT
```

Then run:
```bash
python collect_historical_data.py --symbols-file my_symbols.txt
```

## Data Storage Structure

Data is organized by symbol and timeframe:

```
data/historical/
├── BTC_USDT/
│   ├── 5m/
│   │   ├── data.parquet
│   │   └── metadata.json
│   ├── 15m/
│   │   ├── data.parquet
│   │   └── metadata.json
│   ├── 1h/
│   │   ├── data.parquet
│   │   └── metadata.json
│   ├── 4h/
│   │   ├── data.parquet
│   │   └── metadata.json
│   └── 1d/
│       ├── data.parquet
│       └── metadata.json
├── ETH_USDT/
│   └── ...
└── ...
```

### Parquet Files

Each `data.parquet` file contains:
- **timestamp**: DateTime index
- **open**: Opening price
- **high**: Highest price
- **low**: Lowest price
- **close**: Closing price
- **volume**: Trading volume

### Metadata Files

Each `metadata.json` file contains:
```json
{
  "symbol": "BTC/USDT",
  "timeframe": "5m",
  "start_date": "2021-01-01 00:00:00",
  "end_date": "2024-12-31 23:55:00",
  "total_bars": 420480,
  "collection_time": "2025-01-15T10:30:00"
}
```

## Data Quality Validation

The script automatically validates data quality and reports:

- **Missing timestamps**: Gaps >2x timeframe interval
- **Zero volume bars**: Candles with no trading volume
- **Price anomalies**: Spikes >50% from 20-period moving average
- **Duplicate timestamps**: Duplicate candles (removed automatically)

Quality issues are logged but don't stop collection. The data is still saved for manual review.

## Performance Considerations

### Rate Limiting

- Default: 5 concurrent requests
- Includes 0.1s delay between batches
- Automatic retry with exponential backoff on errors

### Collection Time Estimates

For 50 symbols × 5 timeframes = 250 datasets:

- **5m timeframe**: ~525,000 candles per symbol (2021-2026)
- **1d timeframe**: ~1,870 candles per symbol (2021-2026)
- **Estimated time**: 2-5 hours (depends on exchange rate limits)

### Disk Space

Approximate storage requirements:
- **5m data**: ~5-10 MB per symbol (compressed)
- **1d data**: ~100-200 KB per symbol (compressed)
- **Total for 50 symbols**: ~2-3 GB

## Troubleshooting

### Symbol Not Found

If a symbol is not available on the exchange:
```
✗ SYMBOL/USDT: Error checking volume - Symbol not found
```

**Solution**: Remove the symbol from your list or use a different exchange.

### Rate Limit Errors

If you see rate limit errors:
```
Error fetching SYMBOL data: Rate limit exceeded
```

**Solution**: Reduce `--max-concurrent` value:
```bash
python collect_historical_data.py --max-concurrent 3
```

### Insufficient Volume

If symbols don't meet volume criteria:
```
✗ SYMBOL/USDT: $1,500,000 24h volume (below $2,000,000 threshold)
```

**Solution**: The script automatically filters these out. Add more symbols to your list to ensure 50+ pass the filter.

### Data Gaps

If you see quality warnings about gaps:
```
WARNING: BTC/USDT 5m: Found 3 gaps in data
```

**Solution**: This is normal for exchange maintenance periods. The data is still usable for backtesting.

## Loading Data for Backtesting

To load collected data in your backtest code:

```python
from src.historical_data_collector import HistoricalDataCollector

# Initialize collector
collector = HistoricalDataCollector(exchange, storage_path="./data/historical")

# Load data
df = collector.load_from_parquet("BTC/USDT", "5m")

print(f"Loaded {len(df)} candles")
print(df.head())
```

## Next Steps

After collecting data:

1. **Verify collection**: Check the summary report for success rate
2. **Review quality issues**: Examine any symbols with quality warnings
3. **Run baseline backtest**: Test the backtesting framework with collected data
4. **Parameter optimization**: Use the data for grid search and optimization

## Requirements Validation

This script satisfies the following requirements:

- ✅ **Requirement 6.1**: Collects data for timeframes: 5m, 15m, 1h, 4h, 1d
- ✅ **Requirement 6.2**: Collects data for date range: January 2021 to December 2024
- ✅ **Requirement 6.3**: Collects data for minimum 50 cryptocurrency pairs with 24h volume >$2M
- ✅ **Requirement 6.4**: Uses CCXT library to query exchange APIs
- ✅ **Requirement 6.5**: Identifies gaps in historical data
- ✅ **Requirement 6.6**: Stores data in Parquet format for fast access
- ✅ **Requirement 6.7**: Validates data quality (missing timestamps, zero volume, price anomalies)
- ✅ **Requirement 6.8**: Logs warnings for data anomalies

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Review the quality reports in the output
3. Verify your exchange API is accessible
4. Ensure sufficient disk space is available
