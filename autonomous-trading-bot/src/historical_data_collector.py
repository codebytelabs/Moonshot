"""
Historical OHLCV Data Collector for Backtesting Framework.
Fetches, validates, and stores historical market data in Parquet format.
"""
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger

import pandas as pd
import ccxt.async_support as ccxt_async

from .exchange_ccxt import ExchangeConnector


class DataQualityReport:
    """Report on data quality issues found during validation."""
    
    def __init__(self):
        self.missing_timestamps: List[Tuple[datetime, datetime]] = []
        self.zero_volume_bars: List[datetime] = []
        self.price_anomalies: List[Tuple[datetime, str, float]] = []
        self.duplicate_timestamps: List[datetime] = []
        self.total_bars: int = 0
        self.valid_bars: int = 0
        
    def to_dict(self) -> Dict:
        """Convert report to dictionary."""
        return {
            "total_bars": self.total_bars,
            "valid_bars": self.valid_bars,
            "completeness_pct": (self.valid_bars / self.total_bars * 100) if self.total_bars > 0 else 0,
            "missing_gaps": len(self.missing_timestamps),
            "zero_volume_count": len(self.zero_volume_bars),
            "price_anomaly_count": len(self.price_anomalies),
            "duplicate_count": len(self.duplicate_timestamps),
        }
    
    def has_issues(self) -> bool:
        """Check if any quality issues were found."""
        return (
            len(self.missing_timestamps) > 0 or
            len(self.zero_volume_bars) > 0 or
            len(self.price_anomalies) > 0 or
            len(self.duplicate_timestamps) > 0
        )


class HistoricalDataCollector:
    """
    Collects and stores historical OHLCV data for backtesting.
    
    Features:
    - Fetches data from exchange APIs using CCXT
    - Validates data quality (gaps, anomalies, zero volume)
    - Stores in Parquet format with Snappy compression
    - Supports parallel collection for multiple symbols
    """
    
    # Timeframe to milliseconds mapping
    TIMEFRAME_MS = {
        "1m": 60 * 1000,
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
    }
    
    def __init__(
        self,
        exchange: ExchangeConnector,
        storage_path: str = "./data/historical"
    ):
        """
        Initialize historical data collector.
        
        Args:
            exchange: Exchange connector for fetching data
            storage_path: Base directory for storing Parquet files
        """
        self.exchange = exchange
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"HistoricalDataCollector initialized with storage: {self.storage_path}")
    
    async def collect_symbol_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        batch_size: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol and timeframe.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (5m, 15m, 1h, 4h, 1d)
            start_date: Start date for data collection
            end_date: End date for data collection
            batch_size: Number of candles per API request
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        logger.info(
            f"Collecting {symbol} {timeframe} data from {start_date} to {end_date}"
        )
        
        if timeframe not in self.TIMEFRAME_MS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        all_candles = []
        current_time = int(start_date.timestamp() * 1000)
        end_time = int(end_date.timestamp() * 1000)
        timeframe_ms = self.TIMEFRAME_MS[timeframe]
        
        while current_time < end_time:
            try:
                # Fetch batch of candles
                candles = await self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_time,
                    limit=batch_size
                )
                
                if not candles:
                    logger.warning(f"No data returned for {symbol} at {current_time}")
                    break
                
                all_candles.extend(candles)
                
                # Move to next batch
                last_timestamp = candles[-1][0]
                current_time = last_timestamp + timeframe_ms
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
                logger.debug(
                    f"Fetched {len(candles)} candles for {symbol}, "
                    f"last timestamp: {datetime.fromtimestamp(last_timestamp/1000)}"
                )
                
            except Exception as e:
                logger.error(f"Error fetching {symbol} data at {current_time}: {e}")
                # Continue with next batch
                current_time += timeframe_ms * batch_size
                await asyncio.sleep(1)
        
        if not all_candles:
            logger.warning(f"No data collected for {symbol} {timeframe}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(
            all_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        
        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        
        # Remove duplicates
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        
        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        logger.info(
            f"Collected {len(df)} candles for {symbol} {timeframe} "
            f"({df['timestamp'].min()} to {df['timestamp'].max()})"
        )
        
        return df

    
    async def collect_bulk_data(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime,
        max_concurrent: int = 5
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Fetch data for multiple symbols and timeframes in parallel.
        
        Args:
            symbols: List of trading pairs
            timeframes: List of timeframes to collect
            start_date: Start date for data collection
            end_date: End date for data collection
            max_concurrent: Maximum concurrent API requests
            
        Returns:
            Nested dict: {symbol: {timeframe: DataFrame}}
        """
        logger.info(
            f"Starting bulk collection: {len(symbols)} symbols, "
            f"{len(timeframes)} timeframes, {max_concurrent} concurrent"
        )
        
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def collect_with_semaphore(symbol: str, timeframe: str):
            """Collect data with concurrency control."""
            async with semaphore:
                try:
                    df = await self.collect_symbol_data(
                        symbol, timeframe, start_date, end_date
                    )
                    return symbol, timeframe, df
                except Exception as e:
                    logger.error(f"Failed to collect {symbol} {timeframe}: {e}")
                    return symbol, timeframe, pd.DataFrame()
        
        # Create tasks for all symbol-timeframe combinations
        tasks = [
            collect_with_semaphore(symbol, timeframe)
            for symbol in symbols
            for timeframe in timeframes
        ]
        
        # Execute all tasks
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Organize results
        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                continue
            
            symbol, timeframe, df = result
            if symbol not in results:
                results[symbol] = {}
            results[symbol][timeframe] = df
        
        logger.info(f"Bulk collection completed: {len(results)} symbols processed")
        return results
    
    def validate_data_quality(
        self,
        df: pd.DataFrame,
        timeframe: str,
        symbol: str = "unknown"
    ) -> DataQualityReport:
        """
        Validate data quality and identify issues.
        
        Checks for:
        - Missing timestamps (gaps > 2x timeframe interval)
        - Zero volume bars
        - Price anomalies (spikes > 50% from moving average)
        - Duplicate timestamps
        
        Args:
            df: DataFrame with OHLCV data
            timeframe: Candle timeframe for gap detection
            symbol: Symbol name for logging
            
        Returns:
            DataQualityReport with identified issues
        """
        report = DataQualityReport()
        
        if df.empty:
            logger.warning(f"Empty DataFrame for {symbol} {timeframe}")
            return report
        
        report.total_bars = len(df)
        
        # Check for duplicates
        duplicates = df[df.duplicated(subset=["timestamp"], keep=False)]
        if not duplicates.empty:
            report.duplicate_timestamps = duplicates["timestamp"].tolist()
            logger.warning(
                f"{symbol} {timeframe}: Found {len(duplicates)} duplicate timestamps"
            )
        
        # Check for missing timestamps (gaps)
        if timeframe in self.TIMEFRAME_MS:
            expected_interval = pd.Timedelta(milliseconds=self.TIMEFRAME_MS[timeframe])
            max_gap = expected_interval * 2
            
            time_diffs = df["timestamp"].diff()
            gaps = time_diffs[time_diffs > max_gap]
            
            if not gaps.empty:
                for idx in gaps.index:
                    gap_start = df.loc[idx - 1, "timestamp"]
                    gap_end = df.loc[idx, "timestamp"]
                    report.missing_timestamps.append((gap_start, gap_end))
                
                logger.warning(
                    f"{symbol} {timeframe}: Found {len(gaps)} gaps in data"
                )
        
        # Check for zero volume bars
        zero_volume = df[df["volume"] == 0]
        if not zero_volume.empty:
            report.zero_volume_bars = zero_volume["timestamp"].tolist()
            logger.warning(
                f"{symbol} {timeframe}: Found {len(zero_volume)} zero volume bars"
            )
        
        # Check for price anomalies (spikes > 50% from 20-period MA)
        if len(df) >= 20:
            df_copy = df.copy()
            df_copy["close_ma"] = df_copy["close"].rolling(window=20, min_periods=1).mean()
            df_copy["deviation"] = abs(df_copy["close"] - df_copy["close_ma"]) / df_copy["close_ma"]
            
            anomalies = df_copy[df_copy["deviation"] > 0.5]
            if not anomalies.empty:
                for idx, row in anomalies.iterrows():
                    report.price_anomalies.append((
                        row["timestamp"],
                        "spike",
                        row["deviation"]
                    ))
                
                logger.warning(
                    f"{symbol} {timeframe}: Found {len(anomalies)} price anomalies"
                )
        
        # Calculate valid bars (no issues)
        report.valid_bars = report.total_bars - len(report.zero_volume_bars)
        
        return report
    
    def save_to_parquet(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        compression: str = "snappy"
    ) -> Path:
        """
        Save DataFrame to Parquet file with compression.
        
        File structure: {storage_path}/{symbol}/{timeframe}/data.parquet
        
        Args:
            df: DataFrame to save
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe
            compression: Compression algorithm (snappy, gzip, brotli)
            
        Returns:
            Path to saved file
        """
        if df.empty:
            logger.warning(f"Cannot save empty DataFrame for {symbol} {timeframe}")
            return None
        
        # Create directory structure
        symbol_safe = symbol.replace("/", "_")
        file_dir = self.storage_path / symbol_safe / timeframe
        file_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = file_dir / "data.parquet"
        
        # Save with metadata
        df.to_parquet(
            file_path,
            engine="pyarrow",
            compression=compression,
            index=False
        )
        
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        logger.info(
            f"Saved {len(df)} bars to {file_path} ({file_size_mb:.2f} MB)"
        )
        
        # Save metadata
        metadata = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": str(df["timestamp"].min()),
            "end_date": str(df["timestamp"].max()),
            "total_bars": len(df),
            "collection_time": datetime.now().isoformat(),
        }
        
        metadata_path = file_dir / "metadata.json"
        import json
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return file_path
    
    def load_from_parquet(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[pd.DataFrame]:
        """
        Load historical data from Parquet file.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe
            
        Returns:
            DataFrame with OHLCV data, or None if file doesn't exist
        """
        symbol_safe = symbol.replace("/", "_")
        file_path = self.storage_path / symbol_safe / timeframe / "data.parquet"
        
        if not file_path.exists():
            logger.warning(f"No data file found at {file_path}")
            return None
        
        try:
            df = pd.read_parquet(file_path, engine="pyarrow")
            logger.info(f"Loaded {len(df)} bars from {file_path}")
            return df
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    async def collect_and_save(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        validate: bool = True
    ) -> Tuple[Optional[Path], Optional[DataQualityReport]]:
        """
        Collect data, validate quality, and save to Parquet.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            start_date: Start date
            end_date: End date
            validate: Whether to perform quality validation
            
        Returns:
            Tuple of (file_path, quality_report)
        """
        # Collect data
        df = await self.collect_symbol_data(symbol, timeframe, start_date, end_date)
        
        if df.empty:
            logger.error(f"No data collected for {symbol} {timeframe}")
            return None, None
        
        # Validate quality
        quality_report = None
        if validate:
            quality_report = self.validate_data_quality(df, timeframe, symbol)
            
            if quality_report.has_issues():
                logger.warning(
                    f"{symbol} {timeframe} quality issues: {quality_report.to_dict()}"
                )
        
        # Save to Parquet
        file_path = self.save_to_parquet(df, symbol, timeframe)
        
        return file_path, quality_report
    
    async def collect_bulk_and_save(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime,
        max_concurrent: int = 5,
        validate: bool = True
    ) -> Dict[str, Dict[str, Tuple[Optional[Path], Optional[DataQualityReport]]]]:
        """
        Collect data for multiple symbols/timeframes and save all.
        
        Args:
            symbols: List of trading pairs
            timeframes: List of timeframes
            start_date: Start date
            end_date: End date
            max_concurrent: Maximum concurrent requests
            validate: Whether to validate data quality
            
        Returns:
            Nested dict: {symbol: {timeframe: (file_path, quality_report)}}
        """
        # Collect all data
        bulk_data = await self.collect_bulk_data(
            symbols, timeframes, start_date, end_date, max_concurrent
        )
        
        results = {}
        
        # Save and validate each dataset
        for symbol, timeframe_data in bulk_data.items():
            results[symbol] = {}
            
            for timeframe, df in timeframe_data.items():
                if df.empty:
                    results[symbol][timeframe] = (None, None)
                    continue
                
                # Validate
                quality_report = None
                if validate:
                    quality_report = self.validate_data_quality(df, timeframe, symbol)
                
                # Save
                file_path = self.save_to_parquet(df, symbol, timeframe)
                results[symbol][timeframe] = (file_path, quality_report)
        
        logger.info("Bulk collection and save completed")
        return results
