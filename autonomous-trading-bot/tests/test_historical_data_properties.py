"""
Property-based tests for HistoricalDataCollector.
**Validates: Requirements 6.1, 6.2, 6.3, 6.4**
"""
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from src.historical_data_collector import (
    DataQualityReport,
    HistoricalDataCollector,
)


# Strategies for generating test data
@st.composite
def ohlcv_candle(draw):
    """Generate a valid OHLCV candle."""
    timestamp = draw(st.integers(min_value=1609459200000, max_value=1735689600000))  # 2021-2024
    low = draw(st.floats(min_value=0.01, max_value=100000, allow_nan=False, allow_infinity=False))
    high = draw(st.floats(min_value=low, max_value=low * 2, allow_nan=False, allow_infinity=False))
    open_price = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    close = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    volume = draw(st.floats(min_value=0, max_value=1000000, allow_nan=False, allow_infinity=False))
    
    return [timestamp, open_price, high, low, close, volume]


@st.composite
def ohlcv_data_list(draw, min_size=10, max_size=1000):
    """Generate a list of OHLCV candles with sequential timestamps."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    base_time = draw(st.integers(min_value=1609459200000, max_value=1735689600000))
    interval_ms = draw(st.sampled_from([60000, 300000, 900000, 3600000, 14400000, 86400000]))
    
    candles = []
    for i in range(size):
        timestamp = base_time + i * interval_ms
        low = draw(st.floats(min_value=0.01, max_value=100000, allow_nan=False, allow_infinity=False))
        high = draw(st.floats(min_value=low, max_value=low * 2, allow_nan=False, allow_infinity=False))
        open_price = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
        close = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
        volume = draw(st.floats(min_value=0, max_value=1000000, allow_nan=False, allow_infinity=False))
        
        candles.append([timestamp, open_price, high, low, close, volume])
    
    return candles


class TestDataQualityReportProperties:
    """Property-based tests for DataQualityReport."""
    
    @given(
        total=st.integers(min_value=0, max_value=10000),
        valid=st.integers(min_value=0, max_value=10000)
    )
    @settings(max_examples=10)
    def test_completeness_percentage_range(self, total, valid):
        """
        Property: Completeness percentage is always between 0 and 100.
        **Validates: Requirements 6.4**
        """
        # Ensure valid <= total
        if valid > total:
            valid = total
        
        report = DataQualityReport()
        report.total_bars = total
        report.valid_bars = valid
        
        result = report.to_dict()
        completeness = result["completeness_pct"]
        
        assert 0 <= completeness <= 100
    
    @given(
        zero_volume_count=st.integers(min_value=0, max_value=100),
        anomaly_count=st.integers(min_value=0, max_value=100),
        gap_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=10)
    def test_has_issues_consistency(self, zero_volume_count, anomaly_count, gap_count):
        """
        Property: has_issues() returns True iff any issue count > 0.
        **Validates: Requirements 6.4**
        """
        report = DataQualityReport()
        
        # Add issues
        report.zero_volume_bars = [datetime.now()] * zero_volume_count
        report.price_anomalies = [(datetime.now(), "spike", 0.6)] * anomaly_count
        report.missing_timestamps = [(datetime.now(), datetime.now())] * gap_count
        
        has_any_issues = (zero_volume_count > 0 or anomaly_count > 0 or gap_count > 0)
        
        assert report.has_issues() == has_any_issues


class TestHistoricalDataCollectorProperties:
    """Property-based tests for HistoricalDataCollector."""
    
    @pytest.fixture
    def mock_exchange(self):
        """Create a mock exchange connector."""
        exchange = MagicMock()
        exchange.fetch_ohlcv = AsyncMock()
        return exchange
    
    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def collector(self, mock_exchange, temp_storage):
        """Create a HistoricalDataCollector instance."""
        return HistoricalDataCollector(mock_exchange, temp_storage)
    
    @given(ohlcv_data=ohlcv_data_list(min_size=10, max_size=500))
    @settings(max_examples=10, deadline=5000)
    @pytest.mark.asyncio
    async def test_collect_preserves_data_count(self, collector, mock_exchange, ohlcv_data):
        """
        Property: Collected data has same or fewer rows than input (due to deduplication).
        **Validates: Requirements 6.1, 6.2**
        """
        mock_exchange.fetch_ohlcv.return_value = ohlcv_data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        df = await collector.collect_symbol_data("BTC/USDT", "5m", start_date, end_date)
        
        # After deduplication, should have <= original count
        assert len(df) <= len(ohlcv_data)
        assert len(df) > 0
    
    @given(ohlcv_data=ohlcv_data_list(min_size=10, max_size=500))
    @settings(max_examples=10, deadline=5000)
    @pytest.mark.asyncio
    async def test_collected_data_has_correct_schema(self, collector, mock_exchange, ohlcv_data):
        """
        Property: Collected DataFrame always has correct columns.
        **Validates: Requirements 6.1**
        """
        mock_exchange.fetch_ohlcv.return_value = ohlcv_data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        df = await collector.collect_symbol_data("BTC/USDT", "5m", start_date, end_date)
        
        expected_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        assert list(df.columns) == expected_columns
        assert df["timestamp"].dtype == "datetime64[ns]"
    
    @given(ohlcv_data=ohlcv_data_list(min_size=10, max_size=500))
    @settings(max_examples=10, deadline=5000)
    @pytest.mark.asyncio
    async def test_collected_data_sorted_by_timestamp(self, collector, mock_exchange, ohlcv_data):
        """
        Property: Collected data is always sorted by timestamp ascending.
        **Validates: Requirements 6.1**
        """
        mock_exchange.fetch_ohlcv.return_value = ohlcv_data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        df = await collector.collect_symbol_data("BTC/USDT", "5m", start_date, end_date)
        
        if len(df) > 1:
            # Check that timestamps are monotonically increasing
            assert df["timestamp"].is_monotonic_increasing
    
    @given(ohlcv_data=ohlcv_data_list(min_size=10, max_size=500))
    @settings(max_examples=10, deadline=5000)
    @pytest.mark.asyncio
    async def test_no_duplicate_timestamps(self, collector, mock_exchange, ohlcv_data):
        """
        Property: Collected data never contains duplicate timestamps.
        **Validates: Requirements 6.4**
        """
        mock_exchange.fetch_ohlcv.return_value = ohlcv_data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        df = await collector.collect_symbol_data("BTC/USDT", "5m", start_date, end_date)
        
        assert not df["timestamp"].duplicated().any()
    
    @given(
        ohlcv_data=ohlcv_data_list(min_size=10, max_size=200),
        timeframe=st.sampled_from(["1m", "5m", "15m", "1h", "4h", "1d"])
    )
    @settings(max_examples=10, deadline=5000)
    def test_validate_quality_never_crashes(self, collector, ohlcv_data, timeframe):
        """
        Property: Data quality validation never raises exceptions.
        **Validates: Requirements 6.4**
        """
        # Convert to DataFrame
        df = pd.DataFrame(
            ohlcv_data,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        
        # Should not raise
        report = collector.validate_data_quality(df, timeframe, "TEST/USDT")
        
        assert isinstance(report, DataQualityReport)
        assert report.total_bars == len(df)
    
    @given(ohlcv_data=ohlcv_data_list(min_size=10, max_size=200))
    @settings(max_examples=10, deadline=5000)
    def test_save_and_load_roundtrip(self, collector, ohlcv_data):
        """
        Property: Data saved and loaded is identical (roundtrip).
        **Validates: Requirements 6.3**
        """
        # Convert to DataFrame
        df_original = pd.DataFrame(
            ohlcv_data,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df_original["timestamp"] = pd.to_datetime(df_original["timestamp"], unit="ms")
        
        # Save
        file_path = collector.save_to_parquet(df_original, "TEST/USDT", "5m")
        
        if file_path is None:
            # Empty DataFrame case
            assert df_original.empty
            return
        
        # Load
        df_loaded = collector.load_from_parquet("TEST/USDT", "5m")
        
        assert df_loaded is not None
        assert len(df_loaded) == len(df_original)
        
        # Check data equality (allowing for floating point precision)
        pd.testing.assert_frame_equal(df_original, df_loaded, check_dtype=False)
    
    @given(
        zero_volume_indices=st.lists(
            st.integers(min_value=0, max_value=99),
            min_size=0,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=10)
    def test_zero_volume_detection(self, collector, zero_volume_indices):
        """
        Property: Zero volume bars are correctly detected.
        **Validates: Requirements 6.4**
        """
        # Create data with specific zero volume bars
        timestamps = pd.date_range("2024-01-01", periods=100, freq="5min")
        volumes = [1000.0] * 100
        
        for idx in zero_volume_indices:
            volumes[idx] = 0.0
        
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": range(100, 200),
            "high": range(101, 201),
            "low": range(99, 199),
            "close": range(100, 200),
            "volume": volumes
        })
        
        report = collector.validate_data_quality(df, "5m", "TEST/USDT")
        
        assert len(report.zero_volume_bars) == len(zero_volume_indices)
    
    @given(
        symbol=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=3,
            max_size=10
        ),
        timeframe=st.sampled_from(["5m", "1h", "1d"])
    )
    @settings(max_examples=10)
    def test_file_path_generation(self, collector, symbol, timeframe):
        """
        Property: File paths are always valid and consistent.
        **Validates: Requirements 6.3**
        """
        # Create minimal DataFrame
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="5min"),
            "open": [100] * 10,
            "high": [101] * 10,
            "low": [99] * 10,
            "close": [100] * 10,
            "volume": [1000] * 10
        })
        
        # Add /USDT to make it a valid pair
        test_symbol = f"{symbol}/USDT"
        
        file_path = collector.save_to_parquet(df, test_symbol, timeframe)
        
        if file_path is not None:
            assert file_path.exists()
            assert file_path.suffix == ".parquet"
            assert timeframe in str(file_path)
    
    @given(
        symbols=st.lists(
            st.sampled_from(["BTC/USDT", "ETH/USDT", "SOL/USDT"]),
            min_size=1,
            max_size=3,
            unique=True
        ),
        timeframes=st.lists(
            st.sampled_from(["5m", "1h"]),
            min_size=1,
            max_size=2,
            unique=True
        )
    )
    @settings(max_examples=10, deadline=10000)
    @pytest.mark.asyncio
    async def test_bulk_collection_completeness(
        self, collector, mock_exchange, symbols, timeframes
    ):
        """
        Property: Bulk collection returns data for all requested symbol-timeframe pairs.
        **Validates: Requirements 6.1, 6.2**
        """
        # Mock data
        sample_data = [
            [int(datetime(2024, 1, 1).timestamp() * 1000) + i * 300000, 100, 101, 99, 100, 1000]
            for i in range(10)
        ]
        mock_exchange.fetch_ohlcv.return_value = sample_data
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        results = await collector.collect_bulk_data(
            symbols, timeframes, start_date, end_date, max_concurrent=2
        )
        
        # Check all symbols present
        for symbol in symbols:
            assert symbol in results
            
            # Check all timeframes present for each symbol
            for timeframe in timeframes:
                assert timeframe in results[symbol]
                assert isinstance(results[symbol][timeframe], pd.DataFrame)

    @given(
        gap_count=st.integers(min_value=0, max_value=5),
        timeframe=st.sampled_from(["5m", "15m", "1h", "4h", "1d"]),
        data=st.data()
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_data_gap_detection(self, collector, gap_count, timeframe, data):
        """
        Property 9: Data gap detection
        For any OHLCV dataset, gaps larger than 2x the timeframe interval should be identified and flagged.
        **Validates: Requirements 6.5**
        """
        # Get timeframe interval in milliseconds
        interval_ms = collector.TIMEFRAME_MS[timeframe]

        # Create base data with regular intervals
        base_time = datetime(2024, 1, 1)
        num_candles = 100
        timestamps = []

        # Generate gap positions using st.data()
        gap_positions = []
        if gap_count > 0:
            # Draw unique positions for gaps
            available_positions = list(range(10, num_candles - 10))
            gap_positions = sorted(
                [data.draw(st.sampled_from(available_positions)) for _ in range(min(gap_count, len(available_positions)))]
            )
            # Remove duplicates
            gap_positions = sorted(set(gap_positions))[:gap_count]

        # Generate timestamps with intentional gaps
        current_time = base_time
        for i in range(num_candles):
            timestamps.append(current_time)

            # Add gap at specific positions (3x interval to ensure > 2x threshold)
            if i in gap_positions:
                current_time += timedelta(milliseconds=interval_ms * 3)
            else:
                current_time += timedelta(milliseconds=interval_ms)

        # Create DataFrame
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": [100.0] * num_candles,
            "high": [101.0] * num_candles,
            "low": [99.0] * num_candles,
            "close": [100.0] * num_candles,
            "volume": [1000.0] * num_candles
        })

        # Validate data quality
        report = collector.validate_data_quality(df, timeframe, "TEST/USDT")

        # Property: Number of detected gaps should equal number of intentional gaps
        assert len(report.missing_timestamps) == len(gap_positions), \
            f"Expected {len(gap_positions)} gaps, but found {len(report.missing_timestamps)}"

        # Property: Each detected gap should be larger than 2x the timeframe interval
        expected_interval = timedelta(milliseconds=interval_ms)
        max_gap_threshold = expected_interval * 2

        for gap_start, gap_end in report.missing_timestamps:
            gap_duration = gap_end - gap_start
            assert gap_duration > max_gap_threshold, \
                f"Gap duration {gap_duration} should be > {max_gap_threshold}"

    @given(
        anomaly_count=st.integers(min_value=0, max_value=10),
        base_price=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        data=st.data()
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_price_anomaly_detection(self, collector, anomaly_count, base_price, data):
        """
        Property 10: Price anomaly detection
        For any OHLCV dataset, price spikes exceeding 50% from the 20-period moving average should be flagged as anomalies.
        **Validates: Requirements 6.7**
        """
        # Create dataset with at least 100 candles to ensure stable moving average
        num_candles = 100
        base_time = datetime(2024, 1, 1)
        
        # Generate normal price data with small variations around base price
        timestamps = [base_time + timedelta(minutes=5 * i) for i in range(num_candles)]
        
        # Create prices with small random variations (within ±5% of base price)
        prices = []
        for i in range(num_candles):
            variation = data.draw(st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False))
            price = base_price * (1 + variation)
            prices.append(price)
        
        # Select positions for anomalies (after first 20 candles to ensure MA is established)
        anomaly_positions = []
        if anomaly_count > 0:
            available_positions = list(range(20, num_candles - 5))
            if available_positions:
                # Draw unique positions for anomalies
                selected_positions = []
                for _ in range(min(anomaly_count, len(available_positions))):
                    pos = data.draw(st.sampled_from(available_positions))
                    if pos not in selected_positions:
                        selected_positions.append(pos)
                anomaly_positions = sorted(selected_positions)
        
        # Inject price anomalies (spikes > 50% from expected value)
        for pos in anomaly_positions:
            # Calculate what the 20-period MA would be at this position
            window_prices = prices[max(0, pos-20):pos]
            if window_prices:
                ma_value = sum(window_prices) / len(window_prices)
                # Create spike > 50% above MA (using 60% to ensure it's detected)
                spike_multiplier = data.draw(st.floats(min_value=1.6, max_value=2.5, allow_nan=False, allow_infinity=False))
                prices[pos] = ma_value * spike_multiplier
        
        # Create DataFrame
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000.0] * num_candles
        })
        
        # Validate data quality
        report = collector.validate_data_quality(df, "5m", "TEST/USDT")
        
        # Property: Number of detected anomalies should equal number of injected anomalies
        assert len(report.price_anomalies) == len(anomaly_positions), \
            f"Expected {len(anomaly_positions)} anomalies, but found {len(report.price_anomalies)}"
        
        # Property: Each detected anomaly should have deviation > 50% (0.5)
        for timestamp, anomaly_type, deviation in report.price_anomalies:
            assert deviation > 0.5, \
                f"Anomaly deviation {deviation} should be > 0.5"
            assert anomaly_type == "spike", \
                f"Anomaly type should be 'spike', got '{anomaly_type}'"
        
        # Property: Anomaly timestamps should match injected positions
        detected_indices = []
        for anomaly_timestamp, _, _ in report.price_anomalies:
            # Find the index of this timestamp in the DataFrame
            idx = df[df["timestamp"] == anomaly_timestamp].index
            if len(idx) > 0:
                detected_indices.append(idx[0])
        
        assert sorted(detected_indices) == sorted(anomaly_positions), \
            f"Detected anomaly positions {sorted(detected_indices)} should match injected positions {sorted(anomaly_positions)}"




