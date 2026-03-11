"""
Unit tests for HistoricalDataCollector.
Tests data collection, validation, and storage functionality.
"""
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.historical_data_collector import (
    DataQualityReport,
    HistoricalDataCollector,
)


@pytest.fixture
def mock_exchange():
    """Create a mock exchange connector."""
    exchange = MagicMock()
    exchange.fetch_ohlcv = AsyncMock()
    return exchange


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def collector(mock_exchange, temp_storage):
    """Create a HistoricalDataCollector instance."""
    return HistoricalDataCollector(mock_exchange, temp_storage)


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data."""
    base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
    data = []
    for i in range(100):
        timestamp = base_time + i * 5 * 60 * 1000  # 5-minute intervals
        data.append([
            timestamp,
            100.0 + i * 0.1,  # open
            101.0 + i * 0.1,  # high
            99.0 + i * 0.1,   # low
            100.5 + i * 0.1,  # close
            1000.0 + i * 10   # volume
        ])
    return data


class TestDataQualityReport:
    """Test DataQualityReport functionality."""
    
    def test_empty_report(self):
        """Test empty quality report."""
        report = DataQualityReport()
        assert report.total_bars == 0
        assert report.valid_bars == 0
        assert not report.has_issues()
    
    def test_report_with_issues(self):
        """Test report with quality issues."""
        report = DataQualityReport()
        report.total_bars = 100
        report.valid_bars = 95
        report.zero_volume_bars = [datetime.now()]
        report.price_anomalies = [(datetime.now(), "spike", 0.6)]
        
        assert report.has_issues()
        report_dict = report.to_dict()
        assert report_dict["total_bars"] == 100
        assert report_dict["valid_bars"] == 95
        assert report_dict["zero_volume_count"] == 1
        assert report_dict["price_anomaly_count"] == 1
    
    def test_completeness_calculation(self):
        """Test completeness percentage calculation."""
        report = DataQualityReport()
        report.total_bars = 100
        report.valid_bars = 80
        
        report_dict = report.to_dict()
        assert report_dict["completeness_pct"] == 80.0


class TestHistoricalDataCollector:
    """Test HistoricalDataCollector functionality."""
    
    def test_initialization(self, collector, temp_storage):
        """Test collector initialization."""
        assert collector.storage_path == Path(temp_storage)
        assert collector.storage_path.exists()
    
    @pytest.mark.asyncio
    async def test_collect_symbol_data_success(
        self, collector, mock_exchange, sample_ohlcv_data
    ):
        """Test successful data collection for a single symbol."""
        # Mock exchange response
        mock_exchange.fetch_ohlcv.return_value = sample_ohlcv_data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        df = await collector.collect_symbol_data(
            "BTC/USDT", "5m", start_date, end_date
        )
        
        assert not df.empty
        assert len(df) == 100
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert df["timestamp"].dtype == "datetime64[ns]"
    
    @pytest.mark.asyncio
    async def test_collect_symbol_data_empty_response(self, collector, mock_exchange):
        """Test handling of empty API response."""
        mock_exchange.fetch_ohlcv.return_value = []
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        df = await collector.collect_symbol_data(
            "BTC/USDT", "5m", start_date, end_date
        )
        
        assert df.empty
    
    @pytest.mark.asyncio
    async def test_collect_symbol_data_invalid_timeframe(self, collector):
        """Test error handling for invalid timeframe."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            await collector.collect_symbol_data(
                "BTC/USDT", "invalid", start_date, end_date
            )
    
    @pytest.mark.asyncio
    async def test_collect_symbol_data_removes_duplicates(
        self, collector, mock_exchange
    ):
        """Test that duplicate timestamps are removed."""
        # Create data with duplicates
        base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
        data = [
            [base_time, 100, 101, 99, 100.5, 1000],
            [base_time, 100.1, 101.1, 99.1, 100.6, 1001],  # Duplicate timestamp
            [base_time + 5 * 60 * 1000, 101, 102, 100, 101.5, 1100],
        ]
        mock_exchange.fetch_ohlcv.return_value = data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        df = await collector.collect_symbol_data(
            "BTC/USDT", "5m", start_date, end_date
        )
        
        assert len(df) == 2  # Duplicate removed
        assert not df["timestamp"].duplicated().any()
    
    @pytest.mark.asyncio
    async def test_collect_bulk_data(self, collector, mock_exchange, sample_ohlcv_data):
        """Test parallel collection for multiple symbols."""
        mock_exchange.fetch_ohlcv.return_value = sample_ohlcv_data
        
        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["5m", "1h"]
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        results = await collector.collect_bulk_data(
            symbols, timeframes, start_date, end_date, max_concurrent=2
        )
        
        assert len(results) == 2
        assert "BTC/USDT" in results
        assert "ETH/USDT" in results
        assert "5m" in results["BTC/USDT"]
        assert "1h" in results["BTC/USDT"]
    
    def test_validate_data_quality_clean_data(self, collector):
        """Test validation of clean data with no issues."""
        # Create clean data
        timestamps = pd.date_range("2024-01-01", periods=100, freq="5min")
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": range(100, 200),
            "high": range(101, 201),
            "low": range(99, 199),
            "close": range(100, 200),
            "volume": [1000] * 100
        })
        
        report = collector.validate_data_quality(df, "5m", "BTC/USDT")
        
        assert report.total_bars == 100
        assert report.valid_bars == 100
        assert not report.has_issues()
    
    def test_validate_data_quality_zero_volume(self, collector):
        """Test detection of zero volume bars."""
        timestamps = pd.date_range("2024-01-01", periods=10, freq="5min")
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": range(100, 110),
            "high": range(101, 111),
            "low": range(99, 109),
            "close": range(100, 110),
            "volume": [1000, 0, 1000, 0, 1000, 1000, 0, 1000, 1000, 1000]
        })
        
        report = collector.validate_data_quality(df, "5m", "BTC/USDT")
        
        assert len(report.zero_volume_bars) == 3
        assert report.has_issues()
    
    def test_validate_data_quality_gaps(self, collector):
        """Test detection of missing timestamps (gaps)."""
        # Create data with gaps
        timestamps = [
            pd.Timestamp("2024-01-01 00:00:00"),
            pd.Timestamp("2024-01-01 00:05:00"),
            pd.Timestamp("2024-01-01 00:10:00"),
            pd.Timestamp("2024-01-01 00:30:00"),  # 20-minute gap
            pd.Timestamp("2024-01-01 00:35:00"),
        ]
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": [100, 101, 102, 103, 104],
            "high": [101, 102, 103, 104, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100, 101, 102, 103, 104],
            "volume": [1000] * 5
        })
        
        report = collector.validate_data_quality(df, "5m", "BTC/USDT")
        
        assert len(report.missing_timestamps) > 0
        assert report.has_issues()
    
    def test_validate_data_quality_price_anomalies(self, collector):
        """Test detection of price anomalies."""
        timestamps = pd.date_range("2024-01-01", periods=50, freq="5min")
        close_prices = [100.0] * 50
        close_prices[25] = 200.0  # 100% spike
        
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": close_prices,
            "high": [p + 1 for p in close_prices],
            "low": [p - 1 for p in close_prices],
            "close": close_prices,
            "volume": [1000] * 50
        })
        
        report = collector.validate_data_quality(df, "5m", "BTC/USDT")
        
        assert len(report.price_anomalies) > 0
        assert report.has_issues()
    
    def test_save_to_parquet(self, collector):
        """Test saving data to Parquet file."""
        timestamps = pd.date_range("2024-01-01", periods=100, freq="5min")
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": range(100, 200),
            "high": range(101, 201),
            "low": range(99, 199),
            "close": range(100, 200),
            "volume": [1000] * 100
        })
        
        file_path = collector.save_to_parquet(df, "BTC/USDT", "5m")
        
        assert file_path is not None
        assert file_path.exists()
        assert file_path.suffix == ".parquet"
        
        # Check metadata file
        metadata_path = file_path.parent / "metadata.json"
        assert metadata_path.exists()
        
        with open(metadata_path) as f:
            metadata = json.load(f)
        assert metadata["symbol"] == "BTC/USDT"
        assert metadata["timeframe"] == "5m"
        assert metadata["total_bars"] == 100
    
    def test_save_to_parquet_empty_dataframe(self, collector):
        """Test handling of empty DataFrame save."""
        df = pd.DataFrame()
        file_path = collector.save_to_parquet(df, "BTC/USDT", "5m")
        assert file_path is None
    
    def test_load_from_parquet(self, collector):
        """Test loading data from Parquet file."""
        # First save some data
        timestamps = pd.date_range("2024-01-01", periods=100, freq="5min")
        df_original = pd.DataFrame({
            "timestamp": timestamps,
            "open": range(100, 200),
            "high": range(101, 201),
            "low": range(99, 199),
            "close": range(100, 200),
            "volume": [1000] * 100
        })
        
        collector.save_to_parquet(df_original, "BTC/USDT", "5m")
        
        # Load it back
        df_loaded = collector.load_from_parquet("BTC/USDT", "5m")
        
        assert df_loaded is not None
        assert len(df_loaded) == 100
        assert list(df_loaded.columns) == list(df_original.columns)
    
    def test_load_from_parquet_nonexistent(self, collector):
        """Test loading from non-existent file."""
        df = collector.load_from_parquet("NONEXISTENT/USDT", "5m")
        assert df is None
    
    @pytest.mark.asyncio
    async def test_collect_and_save(self, collector, mock_exchange, sample_ohlcv_data):
        """Test combined collect and save operation."""
        mock_exchange.fetch_ohlcv.return_value = sample_ohlcv_data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        file_path, quality_report = await collector.collect_and_save(
            "BTC/USDT", "5m", start_date, end_date, validate=True
        )
        
        assert file_path is not None
        assert file_path.exists()
        assert quality_report is not None
        assert quality_report.total_bars == 100
    
    @pytest.mark.asyncio
    async def test_collect_bulk_and_save(
        self, collector, mock_exchange, sample_ohlcv_data
    ):
        """Test bulk collection and save operation."""
        mock_exchange.fetch_ohlcv.return_value = sample_ohlcv_data
        
        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["5m", "1h"]
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        results = await collector.collect_bulk_and_save(
            symbols, timeframes, start_date, end_date, max_concurrent=2
        )
        
        assert len(results) == 2
        assert "BTC/USDT" in results
        
        # Check that files were saved
        file_path, quality_report = results["BTC/USDT"]["5m"]
        assert file_path is not None
        assert file_path.exists()
