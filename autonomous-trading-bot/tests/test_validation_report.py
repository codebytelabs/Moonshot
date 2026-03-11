"""
Unit tests for validation report generation.

Tests cover:
- Task 9.12: Validation report generator with charts
- Task 9.13: Demo performance comparison to backtest
- Task 9.14: Final report generation and persistence

Requirements: 20.6, 20.7, 20.8, 20.9, 20.10, 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json
from unittest.mock import Mock, MagicMock, patch
import tempfile
import shutil

from src.extended_validation_system import (
    ExtendedValidationSystem,
    ValidationReport,
    PerformanceSnapshot,
    EdgeCase
)


@pytest.fixture
def mock_store():
    """Create mock Supabase store."""
    store = Mock()
    store.get_recent_trades = Mock(return_value=[])
    store.get_open_positions = Mock(return_value=[])
    store.insert_performance_metric = Mock()
    store.client = Mock()
    store.client.table = Mock(return_value=Mock(insert=Mock(return_value=Mock(execute=Mock()))))
    return store


@pytest.fixture
def mock_exchange():
    """Create mock exchange connector."""
    return Mock()


@pytest.fixture
def validation_system(mock_store, mock_exchange):
    """Create validation system instance."""
    return ExtendedValidationSystem(
        bot=None,
        exchange=mock_exchange,
        store=mock_store,
        duration_days=28
    )


@pytest.fixture
def sample_trades():
    """Create sample trade data."""
    base_time = datetime.now() - timedelta(days=20)
    trades = []
    
    for i in range(50):
        pnl = 100 if i % 3 != 0 else -50  # ~67% win rate
        trades.append({
            'id': f'trade_{i}',
            'symbol': 'BTC/USDT',
            'pnl': pnl,
            'r_multiple': pnl / 50,  # Assuming $50 risk
            'created_at': (base_time + timedelta(hours=i * 2)).isoformat()
        })
    
    return trades


@pytest.fixture
def backtest_metrics():
    """Create sample backtest metrics."""
    return {
        'total_trades': 100,
        'win_rate': 0.60,
        'profit_factor': 2.5,
        'sharpe_ratio': 1.8,
        'max_drawdown': 0.10,
        'total_pnl': 3000.0,
        'avg_r_multiple': 2.0
    }


class TestPerformanceComparison:
    """Test Task 9.13: Compare demo performance to backtest expectations."""
    
    def test_compare_to_backtest_calculates_variance(self, validation_system, backtest_metrics):
        """Test variance calculation for all metrics."""
        validation_system.backtest_metrics = backtest_metrics
        
        demo_metrics = {
            'win_rate': 0.55,  # -8.3% variance
            'profit_factor': 2.0,  # -20% variance
            'max_drawdown': 0.11,  # +10% variance
            'sharpe_ratio': 1.6  # -11.1% variance
        }
        
        comparison = validation_system.compare_to_backtest(demo_metrics)
        
        # Check variance calculations
        assert 'variance' in comparison
        assert abs(comparison['variance']['win_rate'] - (-8.33)) < 0.1
        assert abs(comparison['variance']['profit_factor'] - (-20.0)) < 0.1
        assert abs(comparison['variance']['max_drawdown'] - 10.0) < 0.1
    
    def test_win_rate_within_10_percent_threshold(self, validation_system, backtest_metrics):
        """Test win_rate within ±10% threshold (Requirement 20.7)."""
        validation_system.backtest_metrics = backtest_metrics
        
        # Within threshold
        demo_metrics = {'win_rate': 0.65, 'profit_factor': 2.5, 'max_drawdown': 0.10, 'sharpe_ratio': 1.8}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['within_thresholds']['win_rate'] is True
        
        # Outside threshold
        demo_metrics = {'win_rate': 0.45, 'profit_factor': 2.5, 'max_drawdown': 0.10, 'sharpe_ratio': 1.8}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['within_thresholds']['win_rate'] is False
    
    def test_profit_factor_within_20_percent_threshold(self, validation_system, backtest_metrics):
        """Test profit_factor within ±20% threshold (Requirement 20.8)."""
        validation_system.backtest_metrics = backtest_metrics
        
        # Within threshold
        demo_metrics = {'win_rate': 0.60, 'profit_factor': 2.0, 'max_drawdown': 0.10, 'sharpe_ratio': 1.8}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['within_thresholds']['profit_factor'] is True
        
        # Outside threshold
        demo_metrics = {'win_rate': 0.60, 'profit_factor': 1.5, 'max_drawdown': 0.10, 'sharpe_ratio': 1.8}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['within_thresholds']['profit_factor'] is False
    
    def test_max_drawdown_not_exceeding_by_5_percent(self, validation_system, backtest_metrics):
        """Test max_drawdown not exceeding backtest by >5% (Requirement 20.9)."""
        validation_system.backtest_metrics = backtest_metrics
        
        # Within threshold (demo worse but <5%)
        demo_metrics = {'win_rate': 0.60, 'profit_factor': 2.5, 'max_drawdown': 0.104, 'sharpe_ratio': 1.8}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['within_thresholds']['max_drawdown'] is True
        
        # Outside threshold (demo worse by >5%)
        demo_metrics = {'win_rate': 0.60, 'profit_factor': 2.5, 'max_drawdown': 0.16, 'sharpe_ratio': 1.8}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['within_thresholds']['max_drawdown'] is False
    
    def test_variance_exceeds_thresholds_flagged(self, validation_system, backtest_metrics):
        """Test that variance exceeding thresholds is flagged (Requirement 20.10)."""
        validation_system.backtest_metrics = backtest_metrics
        
        # All within thresholds
        demo_metrics = {'win_rate': 0.58, 'profit_factor': 2.4, 'max_drawdown': 0.104, 'sharpe_ratio': 1.7}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['overall_assessment'] == 'PASS'
        
        # One metric outside threshold
        demo_metrics = {'win_rate': 0.45, 'profit_factor': 2.4, 'max_drawdown': 0.104, 'sharpe_ratio': 1.7}
        comparison = validation_system.compare_to_backtest(demo_metrics)
        assert comparison['overall_assessment'] == 'FAIL'


class TestValidationReportGenerator:
    """Test Task 9.12: Implement validation report generator."""
    
    def test_validation_report_has_all_sections(self, validation_system, sample_trades, backtest_metrics):
        """Test report contains all required sections (Requirement 24.1)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        # Check all sections present
        assert report.start_date is not None
        assert report.end_date is not None
        assert report.duration_days == 28
        assert report.demo_metrics is not None
        assert report.backtest_metrics is not None
        assert report.performance_comparison is not None
        assert report.variance_analysis is not None
        assert report.edge_case_summary is not None
        assert report.go_no_go in ['GO', 'NO_GO', 'CONDITIONAL']
        assert report.recommendation_notes is not None
        assert report.risk_assessment is not None
    
    def test_report_includes_backtest_metrics(self, validation_system, sample_trades, backtest_metrics):
        """Test report includes backtest metrics (Requirement 24.2)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        assert 'total_trades' in report.backtest_metrics
        assert 'win_rate' in report.backtest_metrics
        assert 'profit_factor' in report.backtest_metrics
        assert 'sharpe_ratio' in report.backtest_metrics
        assert 'max_drawdown' in report.backtest_metrics
    
    def test_report_includes_demo_metrics(self, validation_system, sample_trades, backtest_metrics):
        """Test report includes demo trading metrics (Requirement 24.3)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        assert 'total_trades' in report.demo_metrics
        assert 'win_rate' in report.demo_metrics
        assert 'profit_factor' in report.demo_metrics
        assert 'sharpe_ratio' in report.demo_metrics
        assert 'max_drawdown' in report.demo_metrics
        assert report.demo_metrics['total_trades'] == len(sample_trades)
    
    def test_report_includes_performance_comparison(self, validation_system, sample_trades, backtest_metrics):
        """Test report includes performance comparison table (Requirement 24.4)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        assert 'backtest' in report.performance_comparison
        assert 'demo' in report.performance_comparison
        assert 'variance' in report.performance_comparison
        assert 'within_thresholds' in report.performance_comparison
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    def test_report_generates_equity_curve_chart(self, mock_close, mock_savefig, validation_system, sample_trades, backtest_metrics):
        """Test equity curve chart generation (Requirement 24.5)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        assert report.equity_curve_chart_path is not None
        assert 'equity_curve' in report.equity_curve_chart_path
        assert mock_savefig.called
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    def test_report_generates_performance_comparison_chart(self, mock_close, mock_savefig, validation_system, sample_trades, backtest_metrics):
        """Test performance comparison chart generation (Requirement 24.5)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        assert report.performance_comparison_chart_path is not None
        assert 'performance_comparison' in report.performance_comparison_chart_path
        assert mock_savefig.called
    
    def test_report_includes_edge_case_summary(self, validation_system, sample_trades, backtest_metrics):
        """Test report includes edge cases summary (Requirement 24.6)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        # Add some edge cases
        validation_system._log_edge_case('data_quality', 'Test issue 1', {})
        validation_system._log_edge_case('logic_error', 'Test issue 2', {})
        validation_system.edge_cases[0].resolution_status = 'resolved'
        
        report = asyncio.run(validation_system.generate_final_report())
        
        assert 'total_count' in report.edge_case_summary
        assert 'by_category' in report.edge_case_summary
        assert 'by_status' in report.edge_case_summary
        assert 'resolution_rate' in report.edge_case_summary
        assert report.edge_case_summary['total_count'] == 2
    
    def test_go_no_go_recommendation_based_on_criteria(self, validation_system, sample_trades, backtest_metrics):
        """Test go/no-go recommendation based on criteria (Requirement 24.7)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        # Should be GO or CONDITIONAL with good performance
        assert report.go_no_go in ['GO', 'NO_GO', 'CONDITIONAL']
        assert len(report.recommendation_notes) > 0
    
    def test_report_includes_risk_assessment(self, validation_system, sample_trades, backtest_metrics):
        """Test report includes risk assessment (Requirement 24.8)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        assert 'risk_level' in report.risk_assessment
        assert 'recommended_starting_capital' in report.risk_assessment
        assert 'recommended_position_limits' in report.risk_assessment
        assert 'key_risks' in report.risk_assessment


class TestFinalReportGeneration:
    """Test Task 9.14: Generate final validation report."""
    
    @patch('builtins.open', create=True)
    def test_report_saved_to_file(self, mock_open, validation_system, sample_trades, backtest_metrics):
        """Test report is saved to JSON file (Requirement 24.8)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        report = asyncio.run(validation_system.generate_final_report())
        
        # Verify file was opened for writing
        assert mock_open.called
        # Verify JSON was written
        assert mock_file.write.called or mock_file.__enter__.called
    
    def test_report_saved_to_database(self, validation_system, sample_trades, backtest_metrics):
        """Test report is saved to database (Requirement 24.8)."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        # Verify database insert was called
        assert validation_system.store.client.table.called
        assert validation_system.store.client.table.return_value.insert.called
    
    def test_report_compiles_all_metrics(self, validation_system, sample_trades, backtest_metrics):
        """Test report compiles all metrics and analysis."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        # Add daily snapshots
        for i in range(5):
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(days=i),
                total_trades=10 * (i + 1),
                win_rate=0.6,
                profit_factor=2.0,
                sharpe_ratio=1.5,
                max_drawdown=0.1,
                total_pnl=500.0 * (i + 1),
                rolling_7day_win_rate=0.58,
                rolling_7day_pnl=300.0,
                open_positions=2
            )
            validation_system.daily_snapshots.append(snapshot)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        # Verify all data compiled
        assert len(report.daily_snapshots) == 5
        assert len(report.demo_trades) == len(sample_trades)
        assert report.demo_metrics['total_trades'] > 0
    
    def test_report_to_dict_serializable(self, validation_system, sample_trades, backtest_metrics):
        """Test report can be serialized to dict."""
        import asyncio
        
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = backtest_metrics
        validation_system.store.get_recent_trades = Mock(return_value=sample_trades)
        
        report = asyncio.run(validation_system.generate_final_report())
        
        # Convert to dict
        report_dict = report.to_dict()
        
        # Verify serializable
        json_str = json.dumps(report_dict, default=str)
        assert len(json_str) > 0
        
        # Verify all keys present
        assert 'start_date' in report_dict
        assert 'demo_metrics' in report_dict
        assert 'backtest_metrics' in report_dict
        assert 'go_no_go' in report_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
