"""
Property-based tests for Performance Tracker.

Tests universal properties that should hold for all valid inputs.
Uses hypothesis library for property-based testing.

**Validates: Requirements 21.4**
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import numpy as np

from src.performance_tracker import PerformanceTracker


# Strategy for generating valid trade data with timestamps
@st.composite
def trades_with_timestamps(draw):
    """Generate valid trade data with timestamps for testing rolling windows."""
    num_trades = draw(st.integers(min_value=1, max_value=50))
    
    # Generate a base date
    base_date = datetime(2024, 1, 1)
    
    trades = []
    for i in range(num_trades):
        # Generate timestamp within a 30-day window
        days_offset = draw(st.integers(min_value=0, max_value=30))
        hours_offset = draw(st.integers(min_value=0, max_value=23))
        timestamp = base_date + timedelta(days=days_offset, hours=hours_offset)
        
        pnl = draw(st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False))
        r_multiple = draw(st.floats(min_value=-5, max_value=20, allow_nan=False, allow_infinity=False))
        
        trades.append({
            'id': f'trade_{i}',
            'symbol': 'BTC/USDT',
            'pnl': pnl,
            'r_multiple': r_multiple,
            'timestamp': timestamp.isoformat(),
            'status': 'closed',
            'entry_price': 50000.0,
            'exit_price': 50000.0 + pnl,
            'quantity': 0.1
        })
    
    return trades


@st.composite
def window_params(draw):
    """Generate valid window parameters."""
    # Generate end date within reasonable range
    base_date = datetime(2024, 1, 15)  # Middle of our test range
    days_offset = draw(st.integers(min_value=7, max_value=30))
    end_date = base_date + timedelta(days=days_offset)
    
    window_days = draw(st.integers(min_value=1, max_value=14))
    
    return end_date, window_days


class TestPerformanceTrackerProperties:
    """Property-based tests for performance tracker rolling metrics."""
    
    @given(trades_with_timestamps(), window_params())
    @settings(max_examples=5, deadline=None)
    def test_property_42_rolling_metrics_window_boundary(self, all_trades, window_params):
        """
        **Property 42: Rolling metrics calculation**
        **Validates: Requirements 21.4**
        
        Property: For any 7-day window, rolling metrics (win_rate, profit_factor, 
        avg_R_multiple, daily_PnL) should be calculated using only trades within 
        that window.
        
        This test verifies that trades outside the window are excluded.
        """
        end_date, window_days = window_params
        start_date = end_date - timedelta(days=window_days)
        
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Filter trades that should be in the window
        trades_in_window = []
        trades_outside_window = []
        
        for trade in all_trades:
            trade_time = datetime.fromisoformat(trade['timestamp'])
            if start_date <= trade_time <= end_date:
                trades_in_window.append(trade)
            else:
                trades_outside_window.append(trade)
        
        # Mock the database query to return only trades in window
        mock_result = Mock()
        mock_result.data = trades_in_window
        mock_store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        # Create tracker and calculate metrics
        tracker = PerformanceTracker(store=mock_store)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days)
        
        # Verify the correct number of trades were used
        assert metrics['total_trades'] == len(trades_in_window), \
            f"Expected {len(trades_in_window)} trades in window, got {metrics['total_trades']}"
        
        # Verify window boundaries
        assert metrics['window_start'] == start_date.isoformat()
        assert metrics['window_end'] == end_date.isoformat()
    
    @given(trades_with_timestamps(), window_params())
    @settings(max_examples=5, deadline=None)
    def test_property_42_rolling_win_rate_calculation(self, all_trades, window_params):
        """
        **Property 42: Rolling metrics calculation - Win Rate**
        **Validates: Requirements 21.4**
        
        Property: Win rate should be calculated using only trades within the window.
        """
        end_date, window_days = window_params
        start_date = end_date - timedelta(days=window_days)
        
        # Filter trades in window
        trades_in_window = [
            t for t in all_trades 
            if start_date <= datetime.fromisoformat(t['timestamp']) <= end_date
        ]
        
        if not trades_in_window:
            # Skip if no trades in window
            assume(False)
        
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        mock_result = Mock()
        mock_result.data = trades_in_window
        mock_store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        # Calculate expected win rate
        pnls = [float(t['pnl']) for t in trades_in_window]
        winning_trades = [p for p in pnls if p > 0]
        expected_win_rate = (len(winning_trades) / len(pnls) * 100) if pnls else 0.0
        
        # Create tracker and calculate metrics
        tracker = PerformanceTracker(store=mock_store)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days)
        
        # Verify win rate matches expected
        assert abs(metrics['win_rate'] - expected_win_rate) < 0.01, \
            f"Win rate {metrics['win_rate']} doesn't match expected {expected_win_rate}"
    
    @given(trades_with_timestamps(), window_params())
    @settings(max_examples=5, deadline=None)
    def test_property_42_rolling_profit_factor_calculation(self, all_trades, window_params):
        """
        **Property 42: Rolling metrics calculation - Profit Factor**
        **Validates: Requirements 21.4**
        
        Property: Profit factor should be calculated using only trades within the window.
        """
        end_date, window_days = window_params
        start_date = end_date - timedelta(days=window_days)
        
        # Filter trades in window
        trades_in_window = [
            t for t in all_trades 
            if start_date <= datetime.fromisoformat(t['timestamp']) <= end_date
        ]
        
        if not trades_in_window:
            assume(False)
        
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        mock_result = Mock()
        mock_result.data = trades_in_window
        mock_store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        # Calculate expected profit factor
        pnls = [float(t['pnl']) for t in trades_in_window]
        gross_profits = sum([p for p in pnls if p > 0])
        gross_losses = abs(sum([p for p in pnls if p < 0]))
        expected_pf = (gross_profits / gross_losses) if gross_losses > 0 else 0.0
        
        # Create tracker and calculate metrics
        tracker = PerformanceTracker(store=mock_store)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days)
        
        # Verify profit factor matches expected
        assert abs(metrics['profit_factor'] - expected_pf) < 0.01, \
            f"Profit factor {metrics['profit_factor']} doesn't match expected {expected_pf}"
    
    @given(trades_with_timestamps(), window_params())
    @settings(max_examples=5, deadline=None)
    def test_property_42_rolling_avg_r_multiple_calculation(self, all_trades, window_params):
        """
        **Property 42: Rolling metrics calculation - Average R-Multiple**
        **Validates: Requirements 21.4**
        
        Property: Average R-multiple should be calculated using only trades within the window.
        """
        end_date, window_days = window_params
        start_date = end_date - timedelta(days=window_days)
        
        # Filter trades in window
        trades_in_window = [
            t for t in all_trades 
            if start_date <= datetime.fromisoformat(t['timestamp']) <= end_date
        ]
        
        if not trades_in_window:
            assume(False)
        
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        mock_result = Mock()
        mock_result.data = trades_in_window
        mock_store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        # Calculate expected average R-multiple
        r_multiples = [float(t['r_multiple']) for t in trades_in_window]
        expected_avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0
        
        # Create tracker and calculate metrics
        tracker = PerformanceTracker(store=mock_store)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days)
        
        # Verify average R-multiple matches expected
        assert abs(metrics['avg_r_multiple'] - expected_avg_r) < 0.01, \
            f"Average R-multiple {metrics['avg_r_multiple']} doesn't match expected {expected_avg_r}"
    
    @given(trades_with_timestamps(), window_params())
    @settings(max_examples=5, deadline=None)
    def test_property_42_rolling_daily_pnl_calculation(self, all_trades, window_params):
        """
        **Property 42: Rolling metrics calculation - Daily PnL**
        **Validates: Requirements 21.4**
        
        Property: Daily PnL should be calculated using only trades within the window.
        """
        end_date, window_days = window_params
        start_date = end_date - timedelta(days=window_days)
        
        # Filter trades in window
        trades_in_window = [
            t for t in all_trades 
            if start_date <= datetime.fromisoformat(t['timestamp']) <= end_date
        ]
        
        if not trades_in_window:
            assume(False)
        
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        mock_result = Mock()
        mock_result.data = trades_in_window
        mock_store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        # Calculate expected daily PnL
        pnls = [float(t['pnl']) for t in trades_in_window]
        total_pnl = sum(pnls)
        expected_daily_pnl = total_pnl / window_days if window_days > 0 else 0.0
        
        # Create tracker and calculate metrics
        tracker = PerformanceTracker(store=mock_store)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days)
        
        # Verify daily PnL matches expected
        assert abs(metrics['daily_pnl'] - expected_daily_pnl) < 0.01, \
            f"Daily PnL {metrics['daily_pnl']} doesn't match expected {expected_daily_pnl}"
        
        # Verify total PnL matches expected
        assert abs(metrics['total_pnl'] - total_pnl) < 0.01, \
            f"Total PnL {metrics['total_pnl']} doesn't match expected {total_pnl}"
    
    def test_property_42_empty_window(self):
        """
        **Property 42: Rolling metrics with no trades**
        **Validates: Requirements 21.4**
        
        Property: When no trades exist in the window, metrics should return zero values.
        """
        # Create mock store with no trades
        mock_store = Mock()
        mock_store.client = MagicMock()
        mock_result = Mock()
        mock_result.data = []
        mock_store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        tracker = PerformanceTracker(store=mock_store)
        end_date = datetime(2024, 1, 15)
        window_days = 7
        
        metrics = tracker.calculate_rolling_metrics(end_date, window_days)
        
        # Verify all metrics are zero
        assert metrics['win_rate'] == 0.0
        assert metrics['profit_factor'] == 0.0
        assert metrics['avg_r_multiple'] == 0.0
        assert metrics['daily_pnl'] == 0.0
        assert metrics['total_trades'] == 0
        assert metrics['total_pnl'] == 0.0
    
    def test_property_42_seven_day_window_default(self):
        """
        **Property 42: Default 7-day window**
        **Validates: Requirements 21.4**
        
        Property: By default, rolling metrics should use a 7-day window.
        """
        # Create trades spanning 10 days
        base_date = datetime(2024, 1, 1)
        trades = []
        for i in range(10):
            trades.append({
                'id': f'trade_{i}',
                'symbol': 'BTC/USDT',
                'pnl': 100.0,
                'r_multiple': 2.0,
                'timestamp': (base_date + timedelta(days=i)).isoformat(),
                'status': 'closed'
            })
        
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Only trades from last 7 days should be included
        end_date = base_date + timedelta(days=10)
        start_date = end_date - timedelta(days=7)
        
        trades_in_window = [
            t for t in trades 
            if start_date <= datetime.fromisoformat(t['timestamp']) <= end_date
        ]
        
        mock_result = Mock()
        mock_result.data = trades_in_window
        mock_store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        tracker = PerformanceTracker(store=mock_store)
        metrics = tracker.calculate_rolling_metrics(end_date)  # Default window_days=7
        
        # Should have 7 trades (days 4-10 inclusive)
        assert metrics['total_trades'] == len(trades_in_window)
        assert metrics['window_start'] == start_date.isoformat()
        assert metrics['window_end'] == end_date.isoformat()


    @given(st.floats(min_value=0.0, max_value=39.9), st.integers(min_value=10, max_value=100))
    @settings(max_examples=5, deadline=None)
    def test_property_43_performance_degradation_alert(self, win_rate, total_trades):
        """
        **Property 43: Performance degradation alert**
        **Validates: Requirements 21.5**
        
        Property: For any 7-day rolling window, if win_rate drops below 40%, 
        an alert should be triggered.
        """
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Create metrics with win rate below threshold
        end_date = datetime(2024, 1, 15)
        start_date = end_date - timedelta(days=7)
        
        metrics = {
            'win_rate': win_rate,
            'total_trades': total_trades,
            'profit_factor': 1.5,
            'avg_r_multiple': 1.0,
            'daily_pnl': 100.0,
            'total_pnl': 700.0,
            'window_start': start_date.isoformat(),
            'window_end': end_date.isoformat()
        }
        
        # Create tracker and check alerts
        tracker = PerformanceTracker(store=mock_store)
        drawdown = 10.0  # Below drawdown threshold
        alerts = tracker.check_alerts(metrics, drawdown)
        
        # Verify alert was triggered
        assert len(alerts) >= 1, "Expected at least one alert to be triggered"
        
        # Find the win rate alert
        win_rate_alerts = [a for a in alerts if a['type'] == 'win_rate_degradation']
        assert len(win_rate_alerts) == 1, "Expected exactly one win rate degradation alert"
        
        alert = win_rate_alerts[0]
        assert alert['type'] == 'win_rate_degradation'
        assert alert['severity'] == 'warning'
        assert alert['data']['win_rate'] == win_rate
        assert alert['data']['threshold'] == 40.0
        assert alert['data']['total_trades'] == total_trades
        assert '40%' in alert['message']
    
    @given(st.floats(min_value=40.0, max_value=100.0), st.integers(min_value=10, max_value=100))
    @settings(max_examples=5, deadline=None)
    def test_property_43_no_alert_when_win_rate_above_threshold(self, win_rate, total_trades):
        """
        **Property 43: Performance degradation alert - No alert case**
        **Validates: Requirements 21.5**
        
        Property: When win_rate is at or above 40%, no alert should be triggered.
        """
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Create metrics with win rate at or above threshold
        end_date = datetime(2024, 1, 15)
        start_date = end_date - timedelta(days=7)
        
        metrics = {
            'win_rate': win_rate,
            'total_trades': total_trades,
            'profit_factor': 1.5,
            'avg_r_multiple': 1.0,
            'daily_pnl': 100.0,
            'total_pnl': 700.0,
            'window_start': start_date.isoformat(),
            'window_end': end_date.isoformat()
        }
        
        # Create tracker and check alerts
        tracker = PerformanceTracker(store=mock_store)
        drawdown = 10.0  # Below drawdown threshold
        alerts = tracker.check_alerts(metrics, drawdown)
        
        # Verify no win rate alert was triggered
        win_rate_alerts = [a for a in alerts if a['type'] == 'win_rate_degradation']
        assert len(win_rate_alerts) == 0, \
            f"No win rate alert should be triggered when win_rate={win_rate}% >= 40%"
    
    @given(st.floats(min_value=15.01, max_value=50.0))
    @settings(max_examples=5, deadline=None)
    def test_property_44_drawdown_alert(self, drawdown):
        """
        **Property 44: Drawdown alert**
        **Validates: Requirements 21.6**
        
        Property: For any 7-day rolling window, if drawdown exceeds 15%, 
        an alert should be triggered.
        """
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Create metrics with normal win rate
        end_date = datetime(2024, 1, 15)
        start_date = end_date - timedelta(days=7)
        
        metrics = {
            'win_rate': 50.0,  # Above win rate threshold
            'total_trades': 20,
            'profit_factor': 1.5,
            'avg_r_multiple': 1.0,
            'daily_pnl': -50.0,
            'total_pnl': -350.0,
            'window_start': start_date.isoformat(),
            'window_end': end_date.isoformat()
        }
        
        # Create tracker and check alerts with drawdown exceeding threshold
        tracker = PerformanceTracker(store=mock_store)
        alerts = tracker.check_alerts(metrics, drawdown)
        
        # Verify alert was triggered
        assert len(alerts) >= 1, "Expected at least one alert to be triggered"
        
        # Find the drawdown alert
        drawdown_alerts = [a for a in alerts if a['type'] == 'drawdown_exceeded']
        assert len(drawdown_alerts) == 1, "Expected exactly one drawdown alert"
        
        alert = drawdown_alerts[0]
        assert alert['type'] == 'drawdown_exceeded'
        assert alert['severity'] == 'critical'
        assert alert['data']['drawdown'] == drawdown
        assert alert['data']['threshold'] == 15.0
        assert '15%' in alert['message']
    
    @given(st.floats(min_value=0.0, max_value=15.0))
    @settings(max_examples=5, deadline=None)
    def test_property_44_no_alert_when_drawdown_below_threshold(self, drawdown):
        """
        **Property 44: Drawdown alert - No alert case**
        **Validates: Requirements 21.6**
        
        Property: When drawdown is at or below 15%, no alert should be triggered.
        """
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Create metrics with normal win rate
        end_date = datetime(2024, 1, 15)
        start_date = end_date - timedelta(days=7)
        
        metrics = {
            'win_rate': 50.0,  # Above win rate threshold
            'total_trades': 20,
            'profit_factor': 1.5,
            'avg_r_multiple': 1.0,
            'daily_pnl': 100.0,
            'total_pnl': 700.0,
            'window_start': start_date.isoformat(),
            'window_end': end_date.isoformat()
        }
        
        # Create tracker and check alerts with drawdown at or below threshold
        tracker = PerformanceTracker(store=mock_store)
        alerts = tracker.check_alerts(metrics, drawdown)
        
        # Verify no drawdown alert was triggered
        drawdown_alerts = [a for a in alerts if a['type'] == 'drawdown_exceeded']
        assert len(drawdown_alerts) == 0, \
            f"No drawdown alert should be triggered when drawdown={drawdown}% <= 15%"
    
    def test_property_43_and_44_both_alerts_triggered(self):
        """
        **Properties 43 & 44: Both alerts triggered simultaneously**
        **Validates: Requirements 21.5, 21.6**
        
        Property: When both conditions are met (win_rate < 40% AND drawdown > 15%), 
        both alerts should be triggered.
        """
        # Create mock store
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Create metrics with both conditions met
        end_date = datetime(2024, 1, 15)
        start_date = end_date - timedelta(days=7)
        
        metrics = {
            'win_rate': 35.0,  # Below 40%
            'total_trades': 20,
            'profit_factor': 0.8,
            'avg_r_multiple': -0.5,
            'daily_pnl': -100.0,
            'total_pnl': -700.0,
            'window_start': start_date.isoformat(),
            'window_end': end_date.isoformat()
        }
        
        # Create tracker and check alerts with high drawdown
        tracker = PerformanceTracker(store=mock_store)
        drawdown = 20.0  # Above 15%
        alerts = tracker.check_alerts(metrics, drawdown)
        
        # Verify both alerts were triggered
        assert len(alerts) == 2, "Expected both alerts to be triggered"
        
        alert_types = {a['type'] for a in alerts}
        assert 'win_rate_degradation' in alert_types
        assert 'drawdown_exceeded' in alert_types


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
