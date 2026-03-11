"""
Unit tests for PerformanceTracker.

Tests core functionality:
- Rolling metrics calculation
- Alert triggering
- Database updates
- Daily summary generation
- API endpoint support
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from src.performance_tracker import PerformanceTracker


@pytest.fixture
def mock_store():
    """Create mock SupabaseStore."""
    store = Mock()
    store.client = Mock()
    return store


@pytest.fixture
def tracker(mock_store):
    """Create PerformanceTracker with mock store."""
    return PerformanceTracker(store=mock_store)


@pytest.fixture
def sample_trades():
    """Create sample trade data."""
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    trades = []
    for i in range(10):
        trade = {
            "id": f"trade_{i}",
            "symbol": "BTC/USDT",
            "pnl": 100.0 if i % 2 == 0 else -50.0,  # 50% win rate
            "r_multiple": 2.0 if i % 2 == 0 else -1.0,
            "status": "closed",
            "timestamp": (base_time + timedelta(hours=i)).isoformat()
        }
        trades.append(trade)
    
    return trades


class TestPerformanceTracker:
    """Test PerformanceTracker class."""
    
    def test_initialization(self, tracker):
        """Test tracker initializes correctly."""
        assert tracker.store is not None
        assert tracker.alert_callbacks == []
    
    def test_register_alert_callback(self, tracker):
        """Test alert callback registration."""
        callback = Mock()
        tracker.register_alert_callback(callback)
        
        assert len(tracker.alert_callbacks) == 1
        assert tracker.alert_callbacks[0] == callback
    
    def test_get_trades_in_window(self, tracker, sample_trades):
        """Test fetching trades in time window."""
        # Mock database response
        mock_result = Mock()
        mock_result.data = sample_trades
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        end_date = datetime(2024, 1, 2, 12, 0, 0)
        trades = tracker.get_trades_in_window(end_date, window_days=7)
        
        assert len(trades) == 10
        assert trades == sample_trades
    
    def test_calculate_rolling_metrics_with_trades(self, tracker, sample_trades):
        """Test rolling metrics calculation with trades."""
        # Mock database response
        mock_result = Mock()
        mock_result.data = sample_trades
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        end_date = datetime(2024, 1, 2, 12, 0, 0)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days=7)
        
        # Verify metrics
        assert metrics["total_trades"] == 10
        assert metrics["win_rate"] == 50.0  # 5 wins out of 10
        assert metrics["total_pnl"] == 250.0  # 5*100 - 5*50
        assert metrics["avg_r_multiple"] == 0.5  # (5*2 + 5*-1) / 10
        assert "daily_pnl" in metrics
        assert "profit_factor" in metrics
    
    def test_calculate_rolling_metrics_no_trades(self, tracker):
        """Test rolling metrics with no trades."""
        # Mock empty database response
        mock_result = Mock()
        mock_result.data = []
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        end_date = datetime(2024, 1, 2, 12, 0, 0)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days=7)
        
        # Verify zero metrics
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["profit_factor"] == 0.0
        assert metrics["avg_r_multiple"] == 0.0
        assert metrics["daily_pnl"] == 0.0
        assert metrics["total_pnl"] == 0.0
    
    def test_calculate_drawdown(self, tracker, sample_trades):
        """Test drawdown calculation."""
        # Mock database response
        mock_result = Mock()
        mock_result.data = sample_trades
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        end_date = datetime(2024, 1, 2, 12, 0, 0)
        drawdown = tracker.calculate_drawdown(end_date, window_days=7)
        
        # Drawdown should be positive
        assert drawdown >= 0.0
        assert isinstance(drawdown, float)
    
    def test_check_alerts_win_rate_degradation(self, tracker):
        """Test win rate degradation alert."""
        metrics = {
            "win_rate": 35.0,  # Below 40% threshold
            "total_trades": 20,
            "window_start": "2024-01-01",
            "window_end": "2024-01-08"
        }
        drawdown = 10.0
        
        alerts = tracker.check_alerts(metrics, drawdown)
        
        assert len(alerts) == 1
        assert alerts[0]["type"] == "win_rate_degradation"
        assert alerts[0]["severity"] == "warning"
        assert "40%" in alerts[0]["message"]
    
    def test_check_alerts_drawdown_exceeded(self, tracker):
        """Test drawdown exceeded alert."""
        metrics = {
            "win_rate": 50.0,
            "total_trades": 20,
            "window_start": "2024-01-01",
            "window_end": "2024-01-08"
        }
        drawdown = 18.0  # Above 15% threshold
        
        alerts = tracker.check_alerts(metrics, drawdown)
        
        assert len(alerts) == 1
        assert alerts[0]["type"] == "drawdown_exceeded"
        assert alerts[0]["severity"] == "critical"
        assert "15%" in alerts[0]["message"]
    
    def test_check_alerts_both_triggered(self, tracker):
        """Test both alerts triggered simultaneously."""
        metrics = {
            "win_rate": 35.0,  # Below 40%
            "total_trades": 20,
            "window_start": "2024-01-01",
            "window_end": "2024-01-08"
        }
        drawdown = 18.0  # Above 15%
        
        alerts = tracker.check_alerts(metrics, drawdown)
        
        assert len(alerts) == 2
        alert_types = [a["type"] for a in alerts]
        assert "win_rate_degradation" in alert_types
        assert "drawdown_exceeded" in alert_types
    
    def test_check_alerts_no_alerts(self, tracker):
        """Test no alerts when metrics are healthy."""
        metrics = {
            "win_rate": 55.0,  # Above 40%
            "total_trades": 20,
            "window_start": "2024-01-01",
            "window_end": "2024-01-08"
        }
        drawdown = 10.0  # Below 15%
        
        alerts = tracker.check_alerts(metrics, drawdown)
        
        assert len(alerts) == 0
    
    def test_check_alerts_callback_triggered(self, tracker):
        """Test alert callbacks are triggered."""
        callback = Mock()
        tracker.register_alert_callback(callback)
        
        metrics = {
            "win_rate": 35.0,
            "total_trades": 20,
            "window_start": "2024-01-01",
            "window_end": "2024-01-08"
        }
        drawdown = 10.0
        
        alerts = tracker.check_alerts(metrics, drawdown)
        
        # Verify callback was called
        assert callback.call_count == 1
        call_args = callback.call_args[0]
        assert call_args[0] == "win_rate_degradation"
        assert "40%" in call_args[1]
    
    def test_update_performance_metrics_table_insert(self, tracker):
        """Test inserting new performance metrics."""
        # Mock no existing record
        mock_existing = Mock()
        mock_existing.data = []
        tracker.store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_existing
        
        # Mock insert
        mock_insert = Mock()
        tracker.store.client.table.return_value.insert.return_value.execute.return_value = mock_insert
        
        date = datetime(2024, 1, 1)
        metrics = {
            "total_trades": 10,
            "win_rate": 50.0,
            "profit_factor": 2.0,
            "avg_r_multiple": 1.5,
            "daily_pnl": 100.0,
            "total_pnl": 500.0
        }
        
        result = tracker.update_performance_metrics_table(date, metrics)
        
        assert result is True
        tracker.store.client.table.return_value.insert.assert_called_once()
    
    def test_update_performance_metrics_table_update(self, tracker):
        """Test updating existing performance metrics."""
        # Mock existing record
        mock_existing = Mock()
        mock_existing.data = [{"id": "existing_id"}]
        tracker.store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_existing
        
        # Mock update
        mock_update = Mock()
        tracker.store.client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update
        
        date = datetime(2024, 1, 1)
        metrics = {
            "total_trades": 10,
            "win_rate": 50.0,
            "profit_factor": 2.0,
            "avg_r_multiple": 1.5,
            "daily_pnl": 100.0,
            "total_pnl": 500.0
        }
        
        result = tracker.update_performance_metrics_table(date, metrics)
        
        assert result is True
        tracker.store.client.table.return_value.update.assert_called_once()
    
    def test_generate_daily_summary(self, tracker, sample_trades):
        """Test daily summary generation."""
        # Mock trades
        mock_trades = Mock()
        mock_trades.data = sample_trades[:2]  # 2 trades for the day
        
        # Mock open positions
        mock_positions = Mock()
        mock_positions.data = [{"id": "pos1"}, {"id": "pos2"}]
        
        # Setup mock chain
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_trades
        tracker.store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_positions
        
        date = datetime(2024, 1, 1, 12, 0, 0)
        summary = tracker.generate_daily_summary(date)
        
        # Verify summary structure
        assert "date" in summary
        assert "trades_executed" in summary
        assert "open_positions" in summary
        assert "daily_pnl" in summary
        assert "rolling_7day_metrics" in summary
        assert "drawdown_7day" in summary
        assert "alerts" in summary
        assert "timestamp" in summary
    
    def test_get_current_metrics(self, tracker, sample_trades):
        """Test getting current metrics for API."""
        # Mock all trades
        mock_all_trades = Mock()
        mock_all_trades.data = sample_trades
        
        # Mock window trades
        mock_window_trades = Mock()
        mock_window_trades.data = sample_trades
        
        tracker.store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_all_trades
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_window_trades
        
        metrics = tracker.get_current_metrics()
        
        # Verify structure
        assert "rolling_7day" in metrics
        assert "rolling_30day" in metrics
        assert "all_time" in metrics
        assert "equity_curve" in metrics
        assert "timestamp" in metrics
        
        # Verify rolling metrics have drawdown
        assert "drawdown" in metrics["rolling_7day"]
        assert "drawdown" in metrics["rolling_30day"]
        
        # Verify all-time metrics
        assert "total_trades" in metrics["all_time"]
        assert "win_rate" in metrics["all_time"]
        assert "profit_factor" in metrics["all_time"]
    
    def test_build_equity_curve(self, tracker, sample_trades):
        """Test equity curve building."""
        # Mock trades
        mock_result = Mock()
        mock_result.data = sample_trades
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        end_date = datetime(2024, 1, 2, 12, 0, 0)
        curve = tracker._build_equity_curve(end_date, window_days=7)
        
        # Verify curve structure
        assert len(curve) > 0
        assert all("timestamp" in point for point in curve)
        assert all("equity" in point for point in curve)
        
        # Verify equity changes
        assert curve[0]["equity"] == 10000.0  # Starting equity
    
    def test_track_performance_realtime(self, tracker, sample_trades):
        """Test real-time performance tracking."""
        # Mock trades
        mock_result = Mock()
        mock_result.data = sample_trades
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        # Mock existing metrics (for update)
        mock_existing = Mock()
        mock_existing.data = []
        tracker.store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_existing
        
        # Mock insert
        mock_insert = Mock()
        tracker.store.client.table.return_value.insert.return_value.execute.return_value = mock_insert
        
        result = tracker.track_performance_realtime()
        
        # Verify result structure
        assert "metrics" in result
        assert "drawdown" in result
        assert "alerts" in result
        assert "timestamp" in result
    
    def test_profit_factor_calculation(self, tracker):
        """Test profit factor calculation edge cases."""
        # Test with only winning trades
        trades_all_wins = [
            {"pnl": 100.0, "r_multiple": 2.0, "status": "closed", "timestamp": "2024-01-01T12:00:00"},
            {"pnl": 150.0, "r_multiple": 3.0, "status": "closed", "timestamp": "2024-01-01T13:00:00"}
        ]
        
        mock_result = Mock()
        mock_result.data = trades_all_wins
        tracker.store.client.table.return_value.select.return_value.gte.return_value.lte.return_value.eq.return_value.execute.return_value = mock_result
        
        end_date = datetime(2024, 1, 2)
        metrics = tracker.calculate_rolling_metrics(end_date, window_days=7)
        
        # Profit factor should be 0 when no losses
        assert metrics["profit_factor"] == 0.0
        assert metrics["win_rate"] == 100.0
    
    def test_alert_insufficient_trades(self, tracker):
        """Test that alerts don't trigger with insufficient trades."""
        metrics = {
            "win_rate": 30.0,  # Below threshold but...
            "total_trades": 5,  # ...insufficient trades
            "window_start": "2024-01-01",
            "window_end": "2024-01-08"
        }
        drawdown = 10.0
        
        alerts = tracker.check_alerts(metrics, drawdown)
        
        # Should not trigger alert with <10 trades
        assert len(alerts) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
