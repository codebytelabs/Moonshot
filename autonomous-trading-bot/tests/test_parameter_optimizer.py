"""
Unit tests for ParameterOptimizer.

**Validates: Requirements 11.3, 11.5**
"""
import pytest
import pandas as pd
from src.parameter_optimizer import ParameterOptimizer, OptimizationResult


class TestParameterOptimizer:
    """Unit tests for ParameterOptimizer class."""
    
    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance."""
        return ParameterOptimizer(min_trades=30)
    
    @pytest.fixture
    def sample_metrics(self):
        """Sample metrics for testing."""
        return {
            'sharpe_ratio': 1.5,
            'profit_factor': 2.5,
            'win_rate': 55.0
        }
    
    @pytest.fixture
    def sample_results(self):
        """Sample optimization results."""
        return [
            OptimizationResult(
                parameters={'threshold': 0.65},
                metrics={'sharpe_ratio': 1.5, 'profit_factor': 2.5, 'win_rate': 55.0},
                composite_score=0.0,  # Will be calculated
                total_trades=50
            ),
            OptimizationResult(
                parameters={'threshold': 0.70},
                metrics={'sharpe_ratio': 1.8, 'profit_factor': 2.8, 'win_rate': 58.0},
                composite_score=0.0,
                total_trades=45
            ),
            OptimizationResult(
                parameters={'threshold': 0.60},
                metrics={'sharpe_ratio': 1.2, 'profit_factor': 2.2, 'win_rate': 52.0},
                composite_score=0.0,
                total_trades=25  # Below minimum
            )
        ]
    
    def test_initialization(self):
        """Test optimizer initialization."""
        optimizer = ParameterOptimizer(min_trades=40)
        assert optimizer.min_trades == 40
    
    def test_default_min_trades(self):
        """Test default minimum trades value."""
        optimizer = ParameterOptimizer()
        assert optimizer.min_trades == 30
    
    def test_calculate_composite_score_valid(self, optimizer, sample_metrics):
        """Test composite score calculation with valid metrics."""
        score = optimizer.calculate_composite_score(sample_metrics)
        
        # Expected: (1.5 * 0.4) + (2.5 * 0.3) + (55.0 * 0.3)
        # = 0.6 + 0.75 + 16.5 = 17.85
        expected = (1.5 * 0.4) + (2.5 * 0.3) + (55.0 * 0.3)
        assert abs(score - expected) < 0.001
    
    def test_calculate_composite_score_formula(self, optimizer):
        """Test composite score formula weights."""
        metrics = {
            'sharpe_ratio': 2.0,
            'profit_factor': 3.0,
            'win_rate': 60.0
        }
        
        score = optimizer.calculate_composite_score(metrics)
        
        # Verify formula: (sharpe × 0.4) + (profit_factor × 0.3) + (win_rate × 0.3)
        expected = (2.0 * 0.4) + (3.0 * 0.3) + (60.0 * 0.3)
        assert abs(score - expected) < 0.001
    
    def test_calculate_composite_score_missing_metric(self, optimizer):
        """Test composite score with missing required metric."""
        incomplete_metrics = {
            'sharpe_ratio': 1.5,
            'profit_factor': 2.5
            # Missing win_rate
        }
        
        with pytest.raises(ValueError, match="Missing required metrics"):
            optimizer.calculate_composite_score(incomplete_metrics)
    
    def test_calculate_composite_score_zero_values(self, optimizer):
        """Test composite score with zero values."""
        metrics = {
            'sharpe_ratio': 0.0,
            'profit_factor': 0.0,
            'win_rate': 0.0
        }
        
        score = optimizer.calculate_composite_score(metrics)
        assert score == 0.0
    
    def test_calculate_composite_score_negative_values(self, optimizer):
        """Test composite score with negative values."""
        metrics = {
            'sharpe_ratio': -0.5,
            'profit_factor': 0.8,
            'win_rate': 45.0
        }
        
        score = optimizer.calculate_composite_score(metrics)
        expected = (-0.5 * 0.4) + (0.8 * 0.3) + (45.0 * 0.3)
        assert abs(score - expected) < 0.001
    
    def test_rank_results_by_score(self, optimizer, sample_results):
        """Test ranking results by composite score."""
        # Calculate composite scores
        for result in sample_results:
            result.composite_score = optimizer.calculate_composite_score(result.metrics)
        
        ranked = optimizer.rank_results(sample_results)
        
        # Should be sorted by composite score descending
        assert len(ranked) == 2  # One filtered out for low trades
        assert ranked[0].composite_score >= ranked[1].composite_score
    
    def test_rank_results_filters_low_trades(self, optimizer, sample_results):
        """Test that ranking filters results with insufficient trades."""
        for result in sample_results:
            result.composite_score = optimizer.calculate_composite_score(result.metrics)
        
        ranked = optimizer.rank_results(sample_results, validate_min_trades=True)
        
        # Should filter out result with 25 trades (< 30 minimum)
        assert len(ranked) == 2
        assert all(r.total_trades >= 30 for r in ranked)
    
    def test_rank_results_no_validation(self, optimizer, sample_results):
        """Test ranking without trade count validation."""
        for result in sample_results:
            result.composite_score = optimizer.calculate_composite_score(result.metrics)
        
        ranked = optimizer.rank_results(sample_results, validate_min_trades=False)
        
        # Should include all results
        assert len(ranked) == 3
    
    def test_rank_results_empty_list(self, optimizer):
        """Test ranking with empty results list."""
        ranked = optimizer.rank_results([])
        assert ranked == []
    
    def test_rank_results_all_filtered(self, optimizer):
        """Test ranking when all results are filtered."""
        low_trade_results = [
            OptimizationResult(
                parameters={'threshold': 0.65},
                metrics={'sharpe_ratio': 1.5, 'profit_factor': 2.5, 'win_rate': 55.0},
                composite_score=17.85,
                total_trades=10
            ),
            OptimizationResult(
                parameters={'threshold': 0.70},
                metrics={'sharpe_ratio': 1.8, 'profit_factor': 2.8, 'win_rate': 58.0},
                composite_score=18.56,
                total_trades=15
            )
        ]
        
        ranked = optimizer.rank_results(low_trade_results, validate_min_trades=True)
        assert ranked == []
    
    def test_generate_report(self, optimizer, sample_results):
        """Test report generation."""
        for result in sample_results:
            result.composite_score = optimizer.calculate_composite_score(result.metrics)
        
        report = optimizer.generate_report(sample_results, top_n=2)
        
        assert isinstance(report, pd.DataFrame)
        assert len(report) == 2  # Top 2 results
        assert 'rank' in report.columns
        assert 'composite_score' in report.columns
        assert 'total_trades' in report.columns
        assert 'sharpe_ratio' in report.columns
        assert 'profit_factor' in report.columns
        assert 'win_rate' in report.columns
    
    def test_generate_report_ranking(self, optimizer, sample_results):
        """Test that report ranks results correctly."""
        for result in sample_results:
            result.composite_score = optimizer.calculate_composite_score(result.metrics)
        
        report = optimizer.generate_report(sample_results, top_n=3)
        
        # Verify ranking is correct (descending by composite score)
        scores = report['composite_score'].tolist()
        assert scores == sorted(scores, reverse=True)
    
    def test_generate_report_empty_results(self, optimizer):
        """Test report generation with empty results."""
        report = optimizer.generate_report([])
        assert isinstance(report, pd.DataFrame)
        assert len(report) == 0
    
    def test_select_best_result(self, optimizer, sample_results):
        """Test selecting best result."""
        for result in sample_results:
            result.composite_score = optimizer.calculate_composite_score(result.metrics)
        
        best = optimizer.select_best_result(sample_results)
        
        assert best is not None
        assert best.total_trades >= 30
        # Should be the one with highest score among valid results
        valid_results = [r for r in sample_results if r.total_trades >= 30]
        max_score = max(r.composite_score for r in valid_results)
        assert abs(best.composite_score - max_score) < 0.001
    
    def test_select_best_result_none_valid(self, optimizer):
        """Test selecting best when no valid results."""
        low_trade_results = [
            OptimizationResult(
                parameters={'threshold': 0.65},
                metrics={'sharpe_ratio': 1.5, 'profit_factor': 2.5, 'win_rate': 55.0},
                composite_score=17.85,
                total_trades=10
            )
        ]
        
        best = optimizer.select_best_result(low_trade_results)
        assert best is None
    
    def test_compare_results(self, optimizer):
        """Test comparing two results."""
        result_a = OptimizationResult(
            parameters={'threshold': 0.65},
            metrics={'sharpe_ratio': 1.5, 'profit_factor': 2.5, 'win_rate': 55.0},
            composite_score=17.85,
            total_trades=50
        )
        
        result_b = OptimizationResult(
            parameters={'threshold': 0.70},
            metrics={'sharpe_ratio': 1.8, 'profit_factor': 2.8, 'win_rate': 58.0},
            composite_score=18.56,
            total_trades=45
        )
        
        comparison = optimizer.compare_results(result_a, result_b)
        
        assert 'result_a' in comparison
        assert 'result_b' in comparison
        assert 'score_improvement' in comparison
        assert 'score_improvement_pct' in comparison
        assert 'metric_deltas' in comparison
        
        # Verify improvement calculation
        expected_improvement = result_b.composite_score - result_a.composite_score
        assert abs(comparison['score_improvement'] - expected_improvement) < 0.001
    
    def test_compare_results_metric_deltas(self, optimizer):
        """Test that comparison calculates metric deltas correctly."""
        result_a = OptimizationResult(
            parameters={'threshold': 0.65},
            metrics={'sharpe_ratio': 1.5, 'profit_factor': 2.5, 'win_rate': 55.0},
            composite_score=17.85,
            total_trades=50
        )
        
        result_b = OptimizationResult(
            parameters={'threshold': 0.70},
            metrics={'sharpe_ratio': 1.8, 'profit_factor': 2.8, 'win_rate': 58.0},
            composite_score=18.56,
            total_trades=45
        )
        
        comparison = optimizer.compare_results(result_a, result_b)
        
        deltas = comparison['metric_deltas']
        assert abs(deltas['sharpe_ratio'] - 0.3) < 0.001
        assert abs(deltas['profit_factor'] - 0.3) < 0.001
        assert abs(deltas['win_rate'] - 3.0) < 0.001
    
    def test_optimization_result_to_dict(self):
        """Test OptimizationResult to_dict method."""
        result = OptimizationResult(
            parameters={'threshold': 0.65},
            metrics={'sharpe_ratio': 1.5, 'profit_factor': 2.5, 'win_rate': 55.0},
            composite_score=17.85,
            total_trades=50
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['parameters'] == {'threshold': 0.65}
        assert result_dict['composite_score'] == 17.85
        assert result_dict['total_trades'] == 50
        assert 'metrics' in result_dict


class TestCompositeScoreEdgeCases:
    """Test edge cases for composite score calculation."""
    
    @pytest.fixture
    def optimizer(self):
        return ParameterOptimizer()
    
    def test_high_sharpe_low_others(self, optimizer):
        """Test with high Sharpe but low other metrics."""
        metrics = {
            'sharpe_ratio': 5.0,
            'profit_factor': 1.0,
            'win_rate': 40.0
        }
        
        score = optimizer.calculate_composite_score(metrics)
        expected = (5.0 * 0.4) + (1.0 * 0.3) + (40.0 * 0.3)
        assert abs(score - expected) < 0.001
    
    def test_balanced_metrics(self, optimizer):
        """Test with balanced metrics."""
        metrics = {
            'sharpe_ratio': 2.0,
            'profit_factor': 2.0,
            'win_rate': 60.0
        }
        
        score = optimizer.calculate_composite_score(metrics)
        expected = (2.0 * 0.4) + (2.0 * 0.3) + (60.0 * 0.3)
        assert abs(score - expected) < 0.001
    
    def test_very_high_win_rate(self, optimizer):
        """Test with very high win rate."""
        metrics = {
            'sharpe_ratio': 1.0,
            'profit_factor': 1.5,
            'win_rate': 90.0
        }
        
        score = optimizer.calculate_composite_score(metrics)
        expected = (1.0 * 0.4) + (1.5 * 0.3) + (90.0 * 0.3)
        assert abs(score - expected) < 0.001
        # Win rate contributes significantly
        assert score > 27.0



class TestBayesianThresholdOptimization:
    """Test Bayesian threshold optimization method."""
    
    @pytest.fixture
    def optimizer(self):
        return ParameterOptimizer(min_trades=30)
    
    @pytest.fixture
    def mock_backtest_result(self):
        """Create a mock backtest result."""
        class MockBacktestResult:
            def __init__(self, total_trades, win_rate, profit_factor, sharpe_ratio=1.5, total_pnl=10000, max_drawdown=10.0):
                self.total_trades = total_trades
                self.win_rate = win_rate  # As decimal (0.55 = 55%)
                self.profit_factor = profit_factor
                self.sharpe_ratio = sharpe_ratio
                self.total_pnl = total_pnl
                self.max_drawdown = max_drawdown
        
        return MockBacktestResult
    
    @pytest.mark.asyncio
    async def test_optimize_bayesian_threshold_default_thresholds(self, optimizer, mock_backtest_result):
        """Test optimization with default threshold values."""
        from datetime import datetime
        
        # Mock backtest runner that returns different results for different thresholds
        async def mock_runner(threshold):
            # Simulate better performance at 0.65 threshold
            if threshold == 0.65:
                return mock_backtest_result(50, 0.58, 2.5, 1.8, 15000, 8.0)
            elif threshold == 0.70:
                return mock_backtest_result(40, 0.60, 2.3, 1.6, 12000, 9.0)
            else:
                return mock_backtest_result(35, 0.55, 2.0, 1.4, 10000, 10.0)
        
        result = await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner
        )
        
        assert result is not None
        assert 'bayesian_threshold' in result.parameters
        assert result.total_trades >= 30
        assert result.composite_score > 0
    
    @pytest.mark.asyncio
    async def test_optimize_bayesian_threshold_custom_thresholds(self, optimizer, mock_backtest_result):
        """Test optimization with custom threshold values."""
        from datetime import datetime
        
        custom_thresholds = [0.60, 0.65, 0.70]
        
        async def mock_runner(threshold):
            return mock_backtest_result(40, 0.55, 2.2, 1.5, 11000, 9.5)
        
        result = await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner,
            thresholds=custom_thresholds
        )
        
        assert result is not None
        assert result.parameters['bayesian_threshold'] in custom_thresholds
    
    @pytest.mark.asyncio
    async def test_optimize_selects_highest_composite_score(self, optimizer, mock_backtest_result):
        """Test that optimization selects threshold with highest composite score."""
        from datetime import datetime
        
        # Create runner that returns progressively better results
        # Composite score = (sharpe * 0.4) + (pf * 0.3) + (wr * 0.3)
        async def mock_runner(threshold):
            if threshold == 0.50:
                return mock_backtest_result(60, 0.50, 2.0, 1.2, 8000, 12.0)  # score = 16.08
            elif threshold == 0.55:
                return mock_backtest_result(55, 0.52, 2.2, 1.4, 10000, 11.0)  # score = 16.82
            elif threshold == 0.60:
                return mock_backtest_result(50, 0.55, 2.4, 1.6, 12000, 10.0)  # score = 17.86
            elif threshold == 0.65:
                return mock_backtest_result(45, 0.58, 2.6, 2.0, 14000, 9.0)  # score = 18.98
            elif threshold == 0.70:
                return mock_backtest_result(40, 0.60, 2.5, 1.7, 13000, 9.5)  # score = 19.43
            elif threshold == 0.75:
                return mock_backtest_result(35, 0.62, 2.4, 1.6, 11000, 10.0)  # score = 19.96
            else:  # 0.80
                return mock_backtest_result(30, 0.65, 2.2, 1.5, 9000, 11.0)  # score = 20.76 - Highest!
        
        result = await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner
        )
        
        # Should select 0.80 as it has the highest composite score
        # Even though it has exactly min_trades (30), it still qualifies
        assert result.parameters['bayesian_threshold'] == 0.80
        assert result.metrics['win_rate'] == 65.0
        assert result.metrics['profit_factor'] == 2.2
        assert result.metrics['sharpe_ratio'] == 1.5
        assert result.total_trades == 30
    
    @pytest.mark.asyncio
    async def test_optimize_filters_insufficient_trades(self, optimizer, mock_backtest_result):
        """Test that optimization filters results with insufficient trades."""
        from datetime import datetime
        
        # Most thresholds produce insufficient trades
        async def mock_runner(threshold):
            if threshold <= 0.60:
                return mock_backtest_result(50, 0.55, 2.3, 1.5, 11000, 9.0)
            else:
                return mock_backtest_result(20, 0.60, 2.5, 1.6, 8000, 8.0)  # Too few trades
        
        result = await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner
        )
        
        # Should select from thresholds with >=30 trades
        assert result.total_trades >= 30
        assert result.parameters['bayesian_threshold'] <= 0.60
    
    @pytest.mark.asyncio
    async def test_optimize_fallback_when_no_sufficient_trades(self, optimizer, mock_backtest_result):
        """Test fallback when no threshold produces sufficient trades."""
        from datetime import datetime
        
        # All thresholds produce insufficient trades
        async def mock_runner(threshold):
            if threshold == 0.65:
                return mock_backtest_result(25, 0.60, 2.5, 1.8, 10000, 8.0)  # Best score but low trades
            else:
                return mock_backtest_result(20, 0.55, 2.0, 1.5, 8000, 9.0)
        
        result = await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner
        )
        
        # Should still return best result even if below min_trades
        assert result is not None
        assert result.parameters['bayesian_threshold'] == 0.65
        assert result.total_trades == 25
    
    @pytest.mark.asyncio
    async def test_optimize_handles_backtest_errors(self, optimizer, mock_backtest_result):
        """Test that optimization handles backtest errors gracefully."""
        from datetime import datetime
        
        call_count = 0
        
        async def mock_runner(threshold):
            nonlocal call_count
            call_count += 1
            
            if threshold == 0.60:
                raise Exception("Backtest failed")
            else:
                return mock_backtest_result(40, 0.55, 2.2, 1.5, 10000, 9.0)
        
        result = await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner
        )
        
        # Should still return result from successful runs
        assert result is not None
        assert result.parameters['bayesian_threshold'] != 0.60
        assert call_count == 7  # All 7 thresholds attempted
    
    @pytest.mark.asyncio
    async def test_optimize_raises_when_all_fail(self, optimizer):
        """Test that optimization raises error when all backtests fail."""
        from datetime import datetime
        
        async def mock_runner(threshold):
            raise Exception("All backtests failed")
        
        with pytest.raises(ValueError, match="No valid backtest results"):
            await optimizer.optimize_bayesian_threshold(
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                symbols=['BTC/USDT'],
                backtest_runner=mock_runner
            )
    
    @pytest.mark.asyncio
    async def test_optimize_result_contains_all_metrics(self, optimizer, mock_backtest_result):
        """Test that optimization result contains all required metrics."""
        from datetime import datetime
        
        async def mock_runner(threshold):
            return mock_backtest_result(45, 0.57, 2.4, 1.7, 12000, 8.5)
        
        result = await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner
        )
        
        # Verify all required metrics are present
        assert 'sharpe_ratio' in result.metrics
        assert 'profit_factor' in result.metrics
        assert 'win_rate' in result.metrics
        assert 'total_pnl' in result.metrics
        assert 'max_drawdown' in result.metrics
        
        # Verify win_rate is converted to percentage (with floating point tolerance)
        assert abs(result.metrics['win_rate'] - 57.0) < 0.01  # 0.57 * 100
    
    @pytest.mark.asyncio
    async def test_optimize_tests_all_default_thresholds(self, optimizer, mock_backtest_result):
        """Test that optimization tests all 7 default thresholds."""
        from datetime import datetime
        
        tested_thresholds = []
        
        async def mock_runner(threshold):
            tested_thresholds.append(threshold)
            return mock_backtest_result(40, 0.55, 2.2, 1.5, 10000, 9.0)
        
        await optimizer.optimize_bayesian_threshold(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=mock_runner
        )
        
        # Should test all 7 default thresholds
        expected_thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        assert sorted(tested_thresholds) == expected_thresholds


class TestTrailingStopOptimization:
    """Unit tests for trailing stop optimization."""
    
    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance."""
        return ParameterOptimizer(min_trades=30)
    
    @pytest.fixture
    def mock_backtest_result(self):
        """Create mock backtest result with runner trades."""
        class MockBacktestResult:
            def __init__(self, stop_pct):
                self.stop_pct = stop_pct
                # Simulate different performance for different stop values
                # Lower stops = more frequent exits = lower avg R-multiple
                # Higher stops = fewer exits but higher R-multiples
                if stop_pct == 0.15:
                    self.trades = [
                        {'exit_type': 'trailing_stop', 'r_multiple': 2.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.0},
                        {'exit_type': 'trailing_stop', 'r_multiple': 2.8},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.2},
                        {'exit_type': 'trailing_stop', 'r_multiple': 2.7},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 2.9},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.1},
                        {'exit_type': 'trailing_stop', 'r_multiple': 2.6},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.3},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.0},
                    ]
                elif stop_pct == 0.25:
                    self.trades = [
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 5.2},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.8},
                        {'exit_type': 'trailing_stop', 'r_multiple': 6.0},
                        {'exit_type': 'trailing_stop', 'r_multiple': 5.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.2},
                        {'exit_type': 'trailing_stop', 'r_multiple': 5.8},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.9},
                        {'exit_type': 'trailing_stop', 'r_multiple': 5.1},
                        {'exit_type': 'trailing_stop', 'r_multiple': 6.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 5.3},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.7},
                    ]
                elif stop_pct == 0.35:
                    self.trades = [
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.2},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.8},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.9},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.1},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.7},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.3},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.6},
                        {'exit_type': 'trailing_stop', 'r_multiple': 4.0},
                    ]
                else:
                    self.trades = [
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.0},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.5},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.2},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.8},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.3},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.6},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.1},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.7},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.4},
                        {'exit_type': 'trailing_stop', 'r_multiple': 3.9},
                    ]
        
        return MockBacktestResult
    
    @pytest.mark.asyncio
    async def test_optimize_trailing_stop_basic(self, optimizer, mock_backtest_result):
        """Test basic trailing stop optimization."""
        from datetime import datetime
        
        async def backtest_runner(stop_pct):
            return mock_backtest_result(stop_pct)
        
        result = await optimizer.optimize_trailing_stop(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=backtest_runner,
            stop_values=[0.15, 0.25, 0.35],
            min_runner_trades=10
        )
        
        # Should select 0.25 (25%) as it has highest avg R-multiple
        assert result.parameters['trailing_stop_pct'] == 0.25
        assert result.metrics['avg_r_multiple'] > 5.0
        assert result.total_trades >= 10
    
    @pytest.mark.asyncio
    async def test_optimize_trailing_stop_default_values(self, optimizer, mock_backtest_result):
        """Test trailing stop optimization with default stop values."""
        from datetime import datetime
        
        async def backtest_runner(stop_pct):
            return mock_backtest_result(stop_pct)
        
        result = await optimizer.optimize_trailing_stop(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=backtest_runner,
            min_runner_trades=10
        )
        
        # Should test default values: [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
        assert result.parameters['trailing_stop_pct'] in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    
    @pytest.mark.asyncio
    async def test_optimize_trailing_stop_metrics(self, optimizer, mock_backtest_result):
        """Test that trailing stop optimization calculates correct metrics."""
        from datetime import datetime
        
        async def backtest_runner(stop_pct):
            return mock_backtest_result(stop_pct)
        
        result = await optimizer.optimize_trailing_stop(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=backtest_runner,
            stop_values=[0.25],
            min_runner_trades=10
        )
        
        # Verify all required metrics are present
        assert 'avg_r_multiple' in result.metrics
        assert 'pct_above_5r' in result.metrics
        assert 'max_favorable_excursion' in result.metrics
        assert 'runner_count' in result.metrics
        assert 'max_r_multiple' in result.metrics
        assert 'min_r_multiple' in result.metrics
        
        # Verify metrics are reasonable
        assert result.metrics['avg_r_multiple'] > 0
        assert 0 <= result.metrics['pct_above_5r'] <= 100
        assert result.metrics['runner_count'] >= 10
    
    @pytest.mark.asyncio
    async def test_optimize_trailing_stop_insufficient_trades(self, optimizer):
        """Test trailing stop optimization with insufficient runner trades."""
        from datetime import datetime
        
        class MockBacktestResultFewTrades:
            def __init__(self, stop_pct):
                # Only 5 runner trades (below minimum of 10)
                self.trades = [
                    {'exit_type': 'trailing_stop', 'r_multiple': 3.0},
                    {'exit_type': 'trailing_stop', 'r_multiple': 3.5},
                    {'exit_type': 'trailing_stop', 'r_multiple': 3.2},
                    {'exit_type': 'trailing_stop', 'r_multiple': 3.8},
                    {'exit_type': 'trailing_stop', 'r_multiple': 3.3},
                ]
        
        async def backtest_runner(stop_pct):
            return MockBacktestResultFewTrades(stop_pct)
        
        with pytest.raises(ValueError, match="No valid backtest results"):
            await optimizer.optimize_trailing_stop(
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                symbols=['BTC/USDT'],
                backtest_runner=backtest_runner,
                stop_values=[0.25],
                min_runner_trades=10
            )
    
    @pytest.mark.asyncio
    async def test_optimize_trailing_stop_pct_above_5r(self, optimizer, mock_backtest_result):
        """Test that pct_above_5r is calculated correctly."""
        from datetime import datetime
        
        async def backtest_runner(stop_pct):
            return mock_backtest_result(stop_pct)
        
        result = await optimizer.optimize_trailing_stop(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=backtest_runner,
            stop_values=[0.25],  # This has several trades >5R
            min_runner_trades=10
        )
        
        # With 0.25 stop, should have some trades >5R
        assert result.metrics['pct_above_5r'] > 0
    
    @pytest.mark.asyncio
    async def test_optimize_trailing_stop_selects_max_avg_r(self, optimizer):
        """Test that optimization selects stop value with maximum average R-multiple."""
        from datetime import datetime
        
        class MockBacktestResultControlled:
            def __init__(self, stop_pct):
                if stop_pct == 0.20:
                    # Lower avg R-multiple
                    self.trades = [{'exit_type': 'trailing_stop', 'r_multiple': 3.0}] * 15
                elif stop_pct == 0.30:
                    # Higher avg R-multiple (should be selected)
                    self.trades = [{'exit_type': 'trailing_stop', 'r_multiple': 6.0}] * 15
                else:
                    # Medium avg R-multiple
                    self.trades = [{'exit_type': 'trailing_stop', 'r_multiple': 4.0}] * 15
        
        async def backtest_runner(stop_pct):
            return MockBacktestResultControlled(stop_pct)
        
        result = await optimizer.optimize_trailing_stop(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            symbols=['BTC/USDT'],
            backtest_runner=backtest_runner,
            stop_values=[0.20, 0.30, 0.40],
            min_runner_trades=10
        )
        
        # Should select 0.30 as it has highest avg R-multiple (6.0)
        assert result.parameters['trailing_stop_pct'] == 0.30
        assert result.metrics['avg_r_multiple'] == 6.0
    
    def test_generate_trailing_stop_report(self, optimizer):
        """Test trailing stop report generation."""
        results = [
            OptimizationResult(
                parameters={'trailing_stop_pct': 0.15},
                metrics={
                    'avg_r_multiple': 3.0,
                    'pct_above_5r': 10.0,
                    'runner_count': 20,
                    'max_r_multiple': 5.0,
                    'min_r_multiple': 1.5,
                    'max_favorable_excursion': 4.0
                },
                composite_score=3.0,
                total_trades=20
            ),
            OptimizationResult(
                parameters={'trailing_stop_pct': 0.25},
                metrics={
                    'avg_r_multiple': 5.2,
                    'pct_above_5r': 45.0,
                    'runner_count': 22,
                    'max_r_multiple': 8.0,
                    'min_r_multiple': 2.0,
                    'max_favorable_excursion': 6.5
                },
                composite_score=5.2,
                total_trades=22
            ),
            OptimizationResult(
                parameters={'trailing_stop_pct': 0.35},
                metrics={
                    'avg_r_multiple': 4.0,
                    'pct_above_5r': 25.0,
                    'runner_count': 18,
                    'max_r_multiple': 6.5,
                    'min_r_multiple': 1.8,
                    'max_favorable_excursion': 5.0
                },
                composite_score=4.0,
                total_trades=18
            )
        ]
        
        report = optimizer.generate_trailing_stop_report(results)
        
        # Verify report structure
        assert len(report) == 3
        assert 'rank' in report.columns
        assert 'trailing_stop_pct' in report.columns
        assert 'runner_count' in report.columns
        assert 'avg_r_multiple' in report.columns
        assert 'pct_above_5r' in report.columns
        
        # Verify sorting (highest avg_r_multiple first)
        assert report.iloc[0]['trailing_stop_pct'] == '25%'
        assert report.iloc[0]['rank'] == 1
        assert report.iloc[0]['avg_r_multiple'] == 5.2
    
    def test_generate_trailing_stop_report_empty(self, optimizer):
        """Test trailing stop report with empty results."""
        report = optimizer.generate_trailing_stop_report([])
        
        assert len(report) == 0
        assert isinstance(report, pd.DataFrame)
