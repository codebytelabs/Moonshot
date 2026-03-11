"""
Unit tests for WalkForwardAnalyzer.

Tests window generation, degradation analysis, CPCV splits, and overfitting detection.
"""
import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

import sys
sys.path.insert(0, 'autonomous-trading-bot/src')

from walk_forward_analyzer import (
    WalkForwardAnalyzer,
    WindowResult,
    WalkForwardResult
)
from cycle_replay_engine import CycleReplayEngine, BacktestConfig


@pytest.fixture
def mock_backtest_engine():
    """Create mock backtest engine."""
    # Create a minimal mock data loader
    class MockDataLoader:
        def __init__(self):
            self.storage_path = "./test_data"
    
    data_loader = MockDataLoader()
    return CycleReplayEngine(data_loader=data_loader)


@pytest.fixture
def analyzer(mock_backtest_engine):
    """Create WalkForwardAnalyzer instance."""
    return WalkForwardAnalyzer(
        backtest_engine=mock_backtest_engine,
        train_window_months=6,
        test_window_months=2,
        step_size_months=2,
        purge_hours=48
    )


class TestWindowGeneration:
    """Test walk-forward window generation."""
    
    def test_generate_windows_basic(self, analyzer):
        """Test basic window generation."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2022, 1, 1)
        
        windows = analyzer.generate_windows(start_date, end_date)
        
        # Should generate multiple windows
        assert len(windows) > 0
        
        # Each window should have 4 elements
        for window in windows:
            assert len(window) == 4
            train_start, train_end, test_start, test_end = window
            
            # Validate ordering
            assert train_start < train_end
            assert train_end < test_start  # Purge gap
            assert test_start < test_end
    
    def test_window_sizes(self, analyzer):
        """Test that windows have correct sizes."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2022, 1, 1)
        
        windows = analyzer.generate_windows(start_date, end_date)
        
        for train_start, train_end, test_start, test_end in windows:
            # Train window should be ~6 months
            train_days = (train_end - train_start).days
            assert 170 < train_days < 190  # ~180 days ± 10
            
            # Test window should be ~2 months
            test_days = (test_end - test_start).days
            assert 55 < test_days < 65  # ~60 days ± 5
    
    def test_purge_gap(self, analyzer):
        """Test that purge gap exists between train and test."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2022, 1, 1)
        
        windows = analyzer.generate_windows(start_date, end_date)
        
        for train_start, train_end, test_start, test_end in windows:
            # Gap should be 48 hours
            gap = (test_start - train_end).total_seconds() / 3600
            assert gap == 48.0
    
    def test_step_size(self, analyzer):
        """Test that windows step forward correctly."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2022, 6, 1)
        
        windows = analyzer.generate_windows(start_date, end_date)
        
        if len(windows) >= 2:
            # Check step between first two windows
            step_days = (windows[1][0] - windows[0][0]).days
            # Should be ~2 months (60 days)
            assert 55 < step_days < 65
    
    def test_no_windows_short_range(self, analyzer):
        """Test that no windows generated for short date range."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2021, 3, 1)  # Only 2 months
        
        windows = analyzer.generate_windows(start_date, end_date)
        
        # Should generate no windows (need 6+2 months minimum)
        assert len(windows) == 0


class TestDegradationAnalysis:
    """Test performance degradation calculation."""
    
    def test_calculate_degradation_no_degradation(self, analyzer):
        """Test degradation when performance is stable."""
        in_sample = {
            'win_rate': 55.0,
            'profit_factor': 2.2,
            'sharpe_ratio': 1.6
        }
        out_sample = {
            'win_rate': 55.0,
            'profit_factor': 2.2,
            'sharpe_ratio': 1.6
        }
        
        result = analyzer.calculate_degradation(in_sample, out_sample)
        
        assert result['avg_degradation_pct'] == 0.0
        assert result['overfitting_flag'] == False
        assert result['consistency_score'] == 100.0
    
    def test_calculate_degradation_minor(self, analyzer):
        """Test minor degradation (< 20%)."""
        in_sample = {
            'win_rate': 55.0,
            'profit_factor': 2.2,
            'sharpe_ratio': 1.6
        }
        out_sample = {
            'win_rate': 50.0,  # 9% degradation
            'profit_factor': 2.0,  # 9% degradation
            'sharpe_ratio': 1.5  # 6% degradation
        }
        
        result = analyzer.calculate_degradation(in_sample, out_sample)
        
        # Average degradation should be ~8%
        assert 7.0 < result['avg_degradation_pct'] < 9.0
        assert result['overfitting_flag'] == False
        assert result['consistency_score'] > 90.0
    
    def test_calculate_degradation_overfitting(self, analyzer):
        """Test overfitting detection (> 20% degradation)."""
        in_sample = {
            'win_rate': 60.0,
            'profit_factor': 2.5,
            'sharpe_ratio': 2.0
        }
        out_sample = {
            'win_rate': 45.0,  # 25% degradation
            'profit_factor': 1.8,  # 28% degradation
            'sharpe_ratio': 1.4  # 30% degradation
        }
        
        result = analyzer.calculate_degradation(in_sample, out_sample)
        
        # Average degradation should be > 20%
        assert result['avg_degradation_pct'] > 20.0
        assert result['overfitting_flag'] == True
        assert result['consistency_score'] < 80.0
    
    def test_calculate_degradation_improvement(self, analyzer):
        """Test when out-of-sample improves (negative degradation)."""
        in_sample = {
            'win_rate': 50.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.5
        }
        out_sample = {
            'win_rate': 55.0,  # Improvement
            'profit_factor': 2.3,  # Improvement
            'sharpe_ratio': 1.7  # Improvement
        }
        
        result = analyzer.calculate_degradation(in_sample, out_sample)
        
        # Degradation should be negative (improvement)
        assert result['avg_degradation_pct'] < 0.0
        assert result['overfitting_flag'] == False
        assert result['consistency_score'] > 100.0


class TestCPCVSplits:
    """Test CPCV split generation."""
    
    def test_generate_cpcv_splits_basic(self, analyzer):
        """Test basic CPCV split generation."""
        # Create sample data with datetime index (larger dataset to accommodate purging)
        dates = pd.date_range('2021-01-01', periods=5000, freq='5min')
        data = pd.DataFrame({'value': range(5000)}, index=dates)
        
        splits = analyzer.generate_cpcv_splits(data, n_splits=5)
        
        # Should generate 5 splits
        assert len(splits) == 5
        
        # Each split should have train and test indices
        for train_idx, test_idx in splits:
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            
            # No overlap between train and test
            assert len(np.intersect1d(train_idx, test_idx)) == 0
    
    def test_cpcv_purging(self, analyzer):
        """Test that purging removes data near test boundaries."""
        dates = pd.date_range('2021-01-01', periods=5000, freq='5min')
        data = pd.DataFrame({'value': range(5000)}, index=dates)
        
        splits = analyzer.generate_cpcv_splits(data, n_splits=5)
        
        # Calculate purge periods (48 hours / 5 min = 576 periods)
        purge_periods = 48 * 60 // 5
        
        for train_idx, test_idx in splits:
            test_start = test_idx.min()
            test_end = test_idx.max()
            
            # Check that train data is purged near test boundaries
            for idx in train_idx:
                # Train index should be far from test boundaries
                # Allow for edge cases where test_start is at beginning
                if test_start > purge_periods:
                    assert (idx < test_start - purge_periods) or (idx > test_end + purge_periods), \
                        f"Train index {idx} is within purge zone of test [{test_start}, {test_end}]"
                else:
                    # For first split, just check distance from test_end
                    assert idx > test_end + purge_periods or idx < test_start, \
                        f"Train index {idx} is within purge zone of test [{test_start}, {test_end}]"
    
    def test_cpcv_test_size(self, analyzer):
        """Test that test sets are approximately equal size."""
        dates = pd.date_range('2021-01-01', periods=5000, freq='5min')
        data = pd.DataFrame({'value': range(5000)}, index=dates)
        
        splits = analyzer.generate_cpcv_splits(data, n_splits=5)
        
        test_sizes = [len(test_idx) for _, test_idx in splits]
        
        # All test sets should be similar size (~1000 each)
        assert all(950 < size < 1050 for size in test_sizes)
    
    def test_cpcv_different_n_splits(self, analyzer):
        """Test CPCV with different number of splits."""
        dates = pd.date_range('2021-01-01', periods=5000, freq='5min')
        data = pd.DataFrame({'value': range(5000)}, index=dates)
        
        for n_splits in [3, 5, 10]:
            splits = analyzer.generate_cpcv_splits(data, n_splits=n_splits)
            assert len(splits) == n_splits


class TestWalkForwardExecution:
    """Test complete walk-forward analysis execution."""
    
    @pytest.mark.asyncio
    async def test_run_walk_forward_basic(self, analyzer):
        """Test basic walk-forward execution."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2021, 12, 31)
        param_grid = {
            'bayesian_threshold': [0.60, 0.65, 0.70],
            'trailing_stop_pct': [0.20, 0.25, 0.30]
        }
        
        result = await analyzer.run_walk_forward(
            start_date, end_date, param_grid
        )
        
        # Should have results
        assert isinstance(result, WalkForwardResult)
        assert result.total_windows > 0
        assert len(result.window_results) == result.total_windows
    
    @pytest.mark.asyncio
    async def test_run_walk_forward_aggregation(self, analyzer):
        """Test that results are properly aggregated."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2021, 12, 31)
        param_grid = {
            'bayesian_threshold': [0.65],
            'trailing_stop_pct': [0.25]
        }
        
        result = await analyzer.run_walk_forward(
            start_date, end_date, param_grid
        )
        
        # Check aggregated metrics exist
        assert 'win_rate' in result.avg_in_sample_metrics
        assert 'win_rate' in result.avg_out_sample_metrics
        assert 'avg_degradation_pct' in result.avg_degradation
    
    @pytest.mark.asyncio
    async def test_run_walk_forward_short_range(self, analyzer):
        """Test walk-forward with insufficient date range."""
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2021, 3, 1)  # Too short
        param_grid = {'bayesian_threshold': [0.65]}
        
        result = await analyzer.run_walk_forward(
            start_date, end_date, param_grid
        )
        
        # Should return empty result
        assert result.total_windows == 0
        assert len(result.window_results) == 0


class TestWindowResult:
    """Test WindowResult dataclass."""
    
    def test_window_result_creation(self):
        """Test creating WindowResult."""
        result = WindowResult(
            window_id=1,
            train_start=datetime(2021, 1, 1),
            train_end=datetime(2021, 7, 1),
            test_start=datetime(2021, 7, 3),
            test_end=datetime(2021, 9, 1),
            optimized_params={'threshold': 0.65},
            in_sample_metrics={'win_rate': 55.0},
            out_sample_metrics={'win_rate': 52.0},
            degradation={'avg_degradation_pct': 5.5}
        )
        
        assert result.window_id == 1
        assert result.optimized_params['threshold'] == 0.65
    
    def test_window_result_to_dict(self):
        """Test converting WindowResult to dictionary."""
        result = WindowResult(
            window_id=1,
            train_start=datetime(2021, 1, 1),
            train_end=datetime(2021, 7, 1),
            test_start=datetime(2021, 7, 3),
            test_end=datetime(2021, 9, 1),
            optimized_params={'threshold': 0.65},
            in_sample_metrics={'win_rate': 55.0},
            out_sample_metrics={'win_rate': 52.0},
            degradation={'avg_degradation_pct': 5.5}
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict['window_id'] == 1
        assert 'train_start' in result_dict
        assert 'optimized_params' in result_dict


class TestWalkForwardResult:
    """Test WalkForwardResult dataclass."""
    
    def test_walk_forward_result_creation(self):
        """Test creating WalkForwardResult."""
        result = WalkForwardResult(
            total_windows=5,
            train_window_months=6,
            test_window_months=2,
            step_size_months=2,
            window_results=[],
            avg_in_sample_metrics={'win_rate': 55.0},
            avg_out_sample_metrics={'win_rate': 52.0},
            avg_degradation={'avg_degradation_pct': 5.5},
            overfitting_flag=False,
            consistency_score=94.5
        )
        
        assert result.total_windows == 5
        assert result.overfitting_flag is False
        assert result.consistency_score == 94.5
    
    def test_walk_forward_result_to_dict(self):
        """Test converting WalkForwardResult to dictionary."""
        result = WalkForwardResult(
            total_windows=5,
            train_window_months=6,
            test_window_months=2,
            step_size_months=2,
            window_results=[],
            avg_in_sample_metrics={'win_rate': 55.0},
            avg_out_sample_metrics={'win_rate': 52.0},
            avg_degradation={'avg_degradation_pct': 5.5},
            overfitting_flag=False,
            consistency_score=94.5
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict['total_windows'] == 5
        assert result_dict['overfitting_flag'] is False
        assert 'avg_in_sample_metrics' in result_dict


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
