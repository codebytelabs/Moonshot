"""
Unit tests for Extended Validation System.

**Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10**
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from extended_validation_system import (
    ExtendedValidationSystem,
    EdgeCase,
    PerformanceSnapshot,
    ValidationReport
)


@pytest.fixture
def mock_bot():
    """Create mock trading bot."""
    bot = Mock()
    bot.config = {'bayesian_threshold': 0.65}
    return bot


@pytest.fixture
def mock_exchange():
    """Create mock exchange connector."""
    exchange = Mock()
    exchange.create_order = AsyncMock(return_value={'order_id': 'test123'})
    exchange.get_account_balance = AsyncMock(return_value={'USDT': 10000.0})
    return exchange


@pytest.fixture
def mock_store():
    """Create mock Supabase store."""
    store = Mock()
    store.get_recent_trades = Mock(return_value=[])
    store.get_open_positions = Mock(return_value=[])
    store.insert_performance_metric = Mock(return_value={'id': 'metric123'})
    return store


@pytest.fixture
def validation_system(mock_bot, mock_exchange, mock_store):
    """Create ExtendedValidationSystem instance."""
    return ExtendedValidationSystem(
        bot=mock_bot,
        exchange=mock_exchange,
        store=mock_store,
        duration_days=28
    )


class TestEdgeCase:
    """Test EdgeCase dataclass."""
    
    def test_edge_case_creation(self):
        """Test creating an edge case."""
        ec = EdgeCase(
            category="data_quality",
            description="Missing price data",
            context={'symbol': 'BTC/USDT'},
            timestamp=datetime.now()
        )
        
        assert ec.category == "data_quality"
        assert ec.description == "Missing price data"
        assert ec.resolution_status == "open"
    
    def test_edge_case_to_dict(self):
        """Test converting edge case to dictionary."""
        ec = EdgeCase(
            category="API_failure",
            description="Timeout error",
            context={'error': 'timeout'},
            timestamp=datetime.now(),
            resolution_status="resolved",
            resolution_notes="Retry succeeded"
        )
        
        result = ec.to_dict()
        
        assert result['category'] == "API_failure"
        assert result['resolution_status'] == "resolved"
        assert result['resolution_notes'] == "Retry succeeded"


class TestPerformanceSnapshot:
    """Test PerformanceSnapshot dataclass."""
    
    def test_snapshot_creation(self):
        """Test creating a performance snapshot."""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            total_trades=50,
            win_rate=0.60,
            profit_factor=2.5,
            sharpe_ratio=1.8,
            max_drawdown=0.12,
            total_pnl=5000.0,
            rolling_7day_win_rate=0.58,
            rolling_7day_pnl=800.0,
            open_positions=3
        )
        
        assert snapshot.total_trades == 50
        assert snapshot.win_rate == 0.60
        assert snapshot.profit_factor == 2.5
    
    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            total_trades=50,
            win_rate=0.60,
            profit_factor=2.5,
            sharpe_ratio=1.8,
            max_drawdown=0.12,
            total_pnl=5000.0,
            rolling_7day_win_rate=0.58,
            rolling_7day_pnl=800.0,
            open_positions=3
        )
        
        result = snapshot.to_dict()
        
        assert result['total_trades'] == 50
        assert result['win_rate'] == 0.60
        assert 'timestamp' in result


class TestExtendedValidationSystem:
    """Test ExtendedValidationSystem class."""
    
    def test_initialization(self, validation_system):
        """Test system initialization."""
        assert validation_system.duration_days == 28
        assert validation_system.edge_cases == []
        assert validation_system.daily_snapshots == []
    
    @pytest.mark.asyncio
    async def test_track_performance_no_trades(self, validation_system, mock_store):
        """Test performance tracking with no trades."""
        mock_store.get_recent_trades.return_value = []
        
        snapshot = await validation_system.track_performance()
        
        assert snapshot.total_trades == 0
        assert snapshot.win_rate == 0.0
        assert snapshot.profit_factor == 0.0
    
    @pytest.mark.asyncio
    async def test_track_performance_with_trades(self, validation_system, mock_store):
        """Test performance tracking with trades."""
        # Mock trades
        trades = [
            {'pnl': 100.0, 'r_multiple': 2.0, 'created_at': datetime.now().isoformat()},
            {'pnl': -50.0, 'r_multiple': -1.0, 'created_at': datetime.now().isoformat()},
            {'pnl': 150.0, 'r_multiple': 3.0, 'created_at': datetime.now().isoformat()},
            {'pnl': 80.0, 'r_multiple': 1.5, 'created_at': datetime.now().isoformat()},
        ]
        mock_store.get_recent_trades.return_value = trades
        
        snapshot = await validation_system.track_performance()
        
        assert snapshot.total_trades == 4
        assert snapshot.win_rate == 0.75  # 3 wins out of 4
        assert snapshot.total_pnl == 280.0
        assert snapshot.profit_factor > 0
    
    def test_compare_to_backtest_no_backtest_metrics(self, validation_system):
        """Test comparison when no backtest metrics available."""
        demo_metrics = {'win_rate': 0.55, 'profit_factor': 2.0}
        
        result = validation_system.compare_to_backtest(demo_metrics)
        
        assert result == {}
    
    def test_compare_to_backtest_within_thresholds(self, validation_system):
        """Test comparison when demo is within thresholds."""
        validation_system.backtest_metrics = {
            'win_rate': 0.60,
            'profit_factor': 2.5,
            'max_drawdown': 0.10,
            'sharpe_ratio': 1.8
        }
        
        demo_metrics = {
            'win_rate': 0.58,  # -3.3% variance (within 10%)
            'profit_factor': 2.4,  # -4% variance (within 20%)
            'max_drawdown': 0.104,  # +4% variance (within 5%)
            'sharpe_ratio': 1.7  # -5.6% variance (within 20%)
        }
        
        result = validation_system.compare_to_backtest(demo_metrics)
        
        assert result['overall_assessment'] == 'PASS'
        assert result['within_thresholds']['win_rate'] == True
        assert result['within_thresholds']['profit_factor'] == True
    
    def test_compare_to_backtest_exceeds_thresholds(self, validation_system):
        """Test comparison when demo exceeds thresholds."""
        validation_system.backtest_metrics = {
            'win_rate': 0.60,
            'profit_factor': 2.5,
            'max_drawdown': 0.10,
            'sharpe_ratio': 1.8
        }
        
        demo_metrics = {
            'win_rate': 0.48,  # -20% variance (exceeds 10%)
            'profit_factor': 1.8,  # -28% variance (exceeds 20%)
            'max_drawdown': 0.18,  # +80% variance (exceeds 5%)
            'sharpe_ratio': 1.2  # -33% variance (exceeds 20%)
        }
        
        result = validation_system.compare_to_backtest(demo_metrics)
        
        assert result['overall_assessment'] == 'FAIL'
        assert result['within_thresholds']['win_rate'] == False
        assert result['within_thresholds']['profit_factor'] == False
    
    def test_identify_edge_cases(self, validation_system):
        """Test edge case identification."""
        # Add some edge cases
        validation_system.edge_cases = [
            EdgeCase(
                category="data_quality",
                description="Missing data",
                context={},
                timestamp=datetime.now()
            ),
            EdgeCase(
                category="API_failure",
                description="Timeout",
                context={},
                timestamp=datetime.now()
            ),
            EdgeCase(
                category="data_quality",
                description="Invalid price",
                context={},
                timestamp=datetime.now()
            )
        ]
        
        result = validation_system.identify_edge_cases()
        
        assert len(result) == 3
        assert result[0].category == "data_quality"
    
    def test_calculate_demo_metrics_empty(self, validation_system):
        """Test calculating metrics with no trades."""
        result = validation_system._calculate_demo_metrics([])
        
        assert result['total_trades'] == 0
        assert result['win_rate'] == 0.0
        assert result['profit_factor'] == 0.0
    
    def test_calculate_demo_metrics_with_trades(self, validation_system):
        """Test calculating metrics with trades."""
        trades = [
            {'pnl': 100.0, 'r_multiple': 2.0},
            {'pnl': -50.0, 'r_multiple': -1.0},
            {'pnl': 150.0, 'r_multiple': 3.0},
            {'pnl': 80.0, 'r_multiple': 1.5},
            {'pnl': -30.0, 'r_multiple': -0.5},
        ]
        
        result = validation_system._calculate_demo_metrics(trades)
        
        assert result['total_trades'] == 5
        assert result['win_rate'] == 0.60  # 3 wins out of 5
        assert result['total_pnl'] == 250.0
        assert result['profit_factor'] > 0
        assert result['avg_r_multiple'] > 0
    
    def test_calculate_sharpe_ratio(self, validation_system):
        """Test Sharpe ratio calculation."""
        trades = [
            {'pnl': 100.0},
            {'pnl': -50.0},
            {'pnl': 150.0},
            {'pnl': 80.0},
            {'pnl': -30.0},
        ]
        
        sharpe = validation_system._calculate_sharpe_ratio(trades)
        
        assert isinstance(sharpe, float)
        assert sharpe != 0.0
    
    def test_calculate_max_drawdown(self, validation_system):
        """Test max drawdown calculation."""
        trades = [
            {'pnl': 100.0},
            {'pnl': -200.0},  # Creates drawdown
            {'pnl': -100.0},  # Extends drawdown
            {'pnl': 300.0},   # Recovery
        ]
        
        max_dd = validation_system._calculate_max_drawdown(trades)
        
        assert isinstance(max_dd, float)
        assert max_dd >= 0.0
        assert max_dd <= 1.0
    
    def test_summarize_edge_cases(self, validation_system):
        """Test edge case summarization."""
        validation_system.edge_cases = [
            EdgeCase(
                category="data_quality",
                description="Test 1",
                context={},
                timestamp=datetime.now(),
                resolution_status="resolved"
            ),
            EdgeCase(
                category="API_failure",
                description="Test 2",
                context={},
                timestamp=datetime.now(),
                resolution_status="open"
            ),
            EdgeCase(
                category="data_quality",
                description="Test 3",
                context={},
                timestamp=datetime.now(),
                resolution_status="resolved"
            )
        ]
        
        summary = validation_system._summarize_edge_cases()
        
        assert summary['total_count'] == 3
        assert summary['by_category']['data_quality'] == 2
        assert summary['by_category']['API_failure'] == 1
        assert summary['by_status']['resolved'] == 2
        assert summary['by_status']['open'] == 1
        assert summary['resolution_rate'] == 2/3
    
    def test_generate_recommendation_go(self, validation_system):
        """Test recommendation generation - GO case."""
        demo_metrics = {'total_trades': 60, 'win_rate': 0.55}
        performance_comparison = {'overall_assessment': 'PASS'}
        edge_case_summary = {'resolution_rate': 0.95}
        
        go_no_go, notes = validation_system._generate_recommendation(
            demo_metrics,
            performance_comparison,
            edge_case_summary
        )
        
        assert go_no_go == "GO"
        assert "Ready for live deployment" in notes
    
    def test_generate_recommendation_conditional(self, validation_system):
        """Test recommendation generation - CONDITIONAL case."""
        demo_metrics = {'total_trades': 60, 'win_rate': 0.55}
        performance_comparison = {'overall_assessment': 'PASS'}
        edge_case_summary = {'resolution_rate': 0.85}  # Below 90%
        
        go_no_go, notes = validation_system._generate_recommendation(
            demo_metrics,
            performance_comparison,
            edge_case_summary
        )
        
        assert go_no_go == "CONDITIONAL"
        assert "edge cases need review" in notes
    
    def test_generate_recommendation_no_go(self, validation_system):
        """Test recommendation generation - NO_GO case."""
        demo_metrics = {'total_trades': 30, 'win_rate': 0.45}  # Insufficient trades
        performance_comparison = {'overall_assessment': 'FAIL'}
        edge_case_summary = {'resolution_rate': 0.70}
        
        go_no_go, notes = validation_system._generate_recommendation(
            demo_metrics,
            performance_comparison,
            edge_case_summary
        )
        
        assert go_no_go == "NO_GO"
        assert "Validation failed" in notes
    
    def test_determine_risk_level_low(self, validation_system):
        """Test risk level determination - LOW."""
        demo_metrics = {
            'win_rate': 0.60,
            'max_drawdown': 0.08
        }
        edge_case_summary = {'total_count': 3}
        
        risk_level = validation_system._determine_risk_level(demo_metrics, edge_case_summary)
        
        assert risk_level == "LOW"
    
    def test_determine_risk_level_medium(self, validation_system):
        """Test risk level determination - MEDIUM."""
        demo_metrics = {
            'win_rate': 0.52,
            'max_drawdown': 0.13
        }
        edge_case_summary = {'total_count': 8}
        
        risk_level = validation_system._determine_risk_level(demo_metrics, edge_case_summary)
        
        assert risk_level == "MEDIUM"
    
    def test_determine_risk_level_high(self, validation_system):
        """Test risk level determination - HIGH."""
        demo_metrics = {
            'win_rate': 0.45,
            'max_drawdown': 0.20
        }
        edge_case_summary = {'total_count': 15}
        
        risk_level = validation_system._determine_risk_level(demo_metrics, edge_case_summary)
        
        assert risk_level == "HIGH"
    
    def test_recommend_capital(self, validation_system):
        """Test capital recommendation."""
        demo_metrics = {'max_drawdown': 0.15}
        
        capital = validation_system._recommend_capital(demo_metrics)
        
        assert isinstance(capital, float)
        assert capital >= 10000.0  # Should be at least starting capital
    
    def test_recommend_position_limits(self, validation_system):
        """Test position limit recommendations."""
        demo_metrics = {'win_rate': 0.55}
        
        limits = validation_system._recommend_position_limits(demo_metrics)
        
        assert 'max_single_position_pct' in limits
        assert 'max_portfolio_exposure_pct' in limits
        assert 'max_daily_loss_pct' in limits
        assert limits['max_single_position_pct'] <= 0.20
    
    def test_identify_key_risks(self, validation_system):
        """Test key risk identification."""
        demo_metrics = {
            'win_rate': 0.45,  # Below 50%
            'max_drawdown': 0.18,  # High
            'total_trades': 40  # Below 50
        }
        edge_case_summary = {'total_count': 12}  # Many edge cases
        
        risks = validation_system._identify_key_risks(demo_metrics, edge_case_summary)
        
        assert len(risks) > 0
        assert any("Win rate" in r for r in risks)
        assert any("drawdown" in r for r in risks)
    
    def test_analyze_variance(self, validation_system):
        """Test variance analysis."""
        comparison = {
            'variance': {
                'win_rate': -5.0,  # Acceptable
                'profit_factor': -25.0,  # Significant
                'max_drawdown': 3.0  # Acceptable
            },
            'within_thresholds': {
                'win_rate': True,
                'profit_factor': False,
                'max_drawdown': True
            },
            'overall_assessment': 'FAIL'
        }
        
        analysis = validation_system._analyze_variance(comparison)
        
        assert analysis['overall_status'] == 'FAIL'
        assert len(analysis['significant_variances']) == 1
        assert len(analysis['acceptable_variances']) == 2
    
    def test_record_trade_result_success(self, validation_system):
        """Test recording successful trade result."""
        trade = {'pnl': 100.0}
        
        validation_system.record_trade_result(trade)
        
        assert validation_system.consecutive_failures == 0
        assert not validation_system.circuit_breaker_active
    
    def test_record_trade_result_failure(self, validation_system):
        """Test recording failed trade result."""
        trade = {'pnl': -50.0}
        
        validation_system.record_trade_result(trade)
        
        assert validation_system.consecutive_failures == 1
        assert not validation_system.circuit_breaker_active
    
    def test_circuit_breaker_trigger(self, validation_system):
        """Test circuit breaker triggers after 3 consecutive failures."""
        # Record 3 consecutive failures
        for _ in range(3):
            validation_system.record_trade_result({'pnl': -50.0})
        
        # Circuit breaker should be active
        assert validation_system.circuit_breaker_active
        assert validation_system.is_trading_paused()
        assert validation_system.consecutive_failures == 3
        
        # Edge case should be logged
        edge_cases = [ec for ec in validation_system.edge_cases if "Circuit breaker" in ec.description]
        assert len(edge_cases) == 1
        assert edge_cases[0].category == "logic_error"
    
    def test_circuit_breaker_reset_counter_on_success(self, validation_system):
        """Test consecutive failure counter resets on successful trade."""
        # Record 2 failures
        validation_system.record_trade_result({'pnl': -50.0})
        validation_system.record_trade_result({'pnl': -30.0})
        assert validation_system.consecutive_failures == 2
        
        # Record success
        validation_system.record_trade_result({'pnl': 100.0})
        
        # Counter should reset
        assert validation_system.consecutive_failures == 0
        assert not validation_system.circuit_breaker_active
    
    def test_circuit_breaker_requires_manual_reset(self, validation_system):
        """Test circuit breaker requires manual reset."""
        # Trigger circuit breaker
        for _ in range(3):
            validation_system.record_trade_result({'pnl': -50.0})
        
        assert validation_system.circuit_breaker_active
        
        # Record successful trades - circuit breaker should remain active
        for _ in range(5):
            validation_system.record_trade_result({'pnl': 100.0})
        
        assert validation_system.circuit_breaker_active
        assert validation_system.is_trading_paused()
    
    def test_reset_circuit_breaker(self, validation_system):
        """Test manual circuit breaker reset."""
        # Trigger circuit breaker
        for _ in range(3):
            validation_system.record_trade_result({'pnl': -50.0})
        
        assert validation_system.circuit_breaker_active
        
        # Manual reset
        validation_system.reset_circuit_breaker("Manual review completed")
        
        # Circuit breaker should be inactive
        assert not validation_system.circuit_breaker_active
        assert not validation_system.is_trading_paused()
        assert validation_system.consecutive_failures == 0
        
        # Edge case should be marked as resolved
        edge_cases = [ec for ec in validation_system.edge_cases if "Circuit breaker" in ec.description]
        assert len(edge_cases) == 1
        assert edge_cases[0].resolution_status == "resolved"
        assert "Manual review completed" in edge_cases[0].resolution_notes
    
    def test_reset_circuit_breaker_when_not_active(self, validation_system):
        """Test resetting circuit breaker when not active."""
        # Should not raise error
        validation_system.reset_circuit_breaker("Test reset")
        
        assert not validation_system.circuit_breaker_active
    
    @pytest.mark.asyncio
    async def test_generate_final_report(self, validation_system, mock_store):
        """Test final report generation."""
        # Setup
        validation_system.start_date = datetime.now() - timedelta(days=28)
        validation_system.backtest_metrics = {
            'win_rate': 0.60,
            'profit_factor': 2.5,
            'max_drawdown': 0.10,
            'sharpe_ratio': 1.8
        }
        
        # Mock trades
        trades = [
            {'pnl': 100.0, 'r_multiple': 2.0},
            {'pnl': -50.0, 'r_multiple': -1.0},
            {'pnl': 150.0, 'r_multiple': 3.0},
        ]
        mock_store.get_recent_trades.return_value = trades
        
        # Generate report
        report = await validation_system.generate_final_report()
        
        assert isinstance(report, ValidationReport)
        assert report.duration_days == 28
        assert 'total_trades' in report.demo_metrics
        assert report.go_no_go in ['GO', 'NO_GO', 'CONDITIONAL']
        assert len(report.recommendation_notes) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
