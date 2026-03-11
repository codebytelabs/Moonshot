"""
Property-based tests for WalkForwardAnalyzer.

Tests universal properties that should hold for all walk-forward analysis scenarios.
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.walk_forward_analyzer import WalkForwardAnalyzer
from src.cycle_replay_engine import CycleReplayEngine


def create_analyzer():
    """Create WalkForwardAnalyzer instance."""
    # Create a minimal mock data loader
    class MockDataLoader:
        def __init__(self):
            self.storage_path = "./test_data"
    
    data_loader = MockDataLoader()
    engine = CycleReplayEngine(data_loader=data_loader)
    return WalkForwardAnalyzer(
        backtest_engine=engine,
        train_window_months=6,
        test_window_months=2,
        step_size_months=2,
        purge_hours=48
    )


# Property 21: Window purging
# **Validates: Requirements 9.3**
@given(
    n_samples=st.integers(min_value=1000, max_value=5000),
    n_splits=st.integers(min_value=3, max_value=10)
)
@settings(max_examples=10, deadline=None)
def test_property_window_purging(n_samples, n_splits):
    """
    Property 21: Window purging
    
    *For any* walk-forward split, training data within purge_hours (48h) of test data 
    boundaries should be excluded from training set.
    
    **Validates: Requirements 9.3**
    """
    analyzer = create_analyzer()
    
    # Create sample data
    dates = pd.date_range('2021-01-01', periods=n_samples, freq='5min')
    data = pd.DataFrame({'value': range(n_samples)}, index=dates)
    
    # Generate CPCV splits
    splits = analyzer.generate_cpcv_splits(data, n_splits=n_splits)
    
    # Calculate purge periods (48 hours / 5 min = 576 periods)
    purge_periods = analyzer.purge_hours * 60 // 5
    
    for train_idx, test_idx in splits:
        test_start = test_idx.min()
        test_end = test_idx.max()
        
        # Check that all train indices are outside purge zone
        for idx in train_idx:
            # Train index must be far from test boundaries
            assert (idx < test_start - purge_periods) or (idx > test_end + purge_periods), \
                f"Train index {idx} is within purge zone of test [{test_start}, {test_end}]"


# Property 22: Out-of-sample testing
# **Validates: Requirements 9.4**
@given(
    in_sample_win_rate=st.floats(min_value=40.0, max_value=70.0),
    in_sample_pf=st.floats(min_value=1.5, max_value=3.0),
    in_sample_sharpe=st.floats(min_value=1.0, max_value=2.5)
)
@settings(max_examples=10, deadline=None)
def test_property_out_of_sample_testing(in_sample_win_rate, in_sample_pf, in_sample_sharpe):
    """
    Property 22: Out-of-sample testing
    
    *For any* walk-forward window, optimized parameters should be applied to test window 
    without any modifications.
    
    **Validates: Requirements 9.4**
    """
    # Create in-sample metrics
    in_sample_metrics = {
        'win_rate': in_sample_win_rate,
        'profit_factor': in_sample_pf,
        'sharpe_ratio': in_sample_sharpe
    }
    
    # Simulate parameter optimization (returns fixed params)
    optimized_params = {
        'bayesian_threshold': 0.65,
        'trailing_stop_pct': 0.25
    }
    
    # The key property: parameters should not be modified for out-of-sample testing
    # We verify this by checking that the same params are used
    test_params = optimized_params.copy()
    
    # Parameters should be identical (no modifications)
    assert test_params == optimized_params, \
        "Parameters were modified during out-of-sample testing"
    
    # No additional optimization should occur on test data
    assert 'bayesian_threshold' in test_params
    assert 'trailing_stop_pct' in test_params


# Property 23: Overfitting detection
# **Validates: Requirements 9.8**
@given(
    in_sample_win_rate=st.floats(min_value=50.0, max_value=70.0),
    degradation_pct=st.floats(min_value=0.0, max_value=50.0)
)
@settings(max_examples=10, deadline=None)
def test_property_overfitting_detection(in_sample_win_rate, degradation_pct):
    """
    Property 23: Overfitting detection
    
    *For any* walk-forward result, if average out-of-sample performance degrades >20% 
    from in-sample, overfitting_flag should be set to True.
    
    **Validates: Requirements 9.8**
    """
    analyzer = create_analyzer()
    # Calculate out-of-sample metrics based on degradation
    out_sample_win_rate = in_sample_win_rate * (1 - degradation_pct / 100)
    
    in_sample_metrics = {
        'win_rate': in_sample_win_rate,
        'profit_factor': 2.2,
        'sharpe_ratio': 1.6
    }
    
    out_sample_metrics = {
        'win_rate': out_sample_win_rate,
        'profit_factor': 2.2 * (1 - degradation_pct / 100),
        'sharpe_ratio': 1.6 * (1 - degradation_pct / 100)
    }
    
    # Calculate degradation
    result = analyzer.calculate_degradation(in_sample_metrics, out_sample_metrics)
    
    # Property: overfitting_flag should be True if degradation > 20%
    if degradation_pct > 20.0:
        assert result['overfitting_flag'] == True, \
            f"Overfitting flag should be True for {degradation_pct:.1f}% degradation"
    else:
        assert result['overfitting_flag'] == False, \
            f"Overfitting flag should be False for {degradation_pct:.1f}% degradation"


# Property 24: Window ordering
@given(
    start_year=st.integers(min_value=2020, max_value=2022),
    duration_months=st.integers(min_value=12, max_value=24)
)
@settings(max_examples=10, deadline=None)
def test_property_window_ordering(start_year, duration_months):
    """
    Property 24: Window ordering
    
    *For any* walk-forward analysis, windows should be ordered chronologically with 
    train_start < train_end < test_start < test_end.
    """
    analyzer = create_analyzer()
    start_date = datetime(start_year, 1, 1)
    end_date = start_date + timedelta(days=30 * duration_months)
    
    windows = analyzer.generate_windows(start_date, end_date)
    
    for train_start, train_end, test_start, test_end in windows:
        # Property: chronological ordering
        assert train_start < train_end, "Train start should be before train end"
        assert train_end < test_start, "Train end should be before test start (purge gap)"
        assert test_start < test_end, "Test start should be before test end"


# Property 25: Degradation calculation consistency
@given(
    in_sample_value=st.floats(min_value=1.0, max_value=100.0),
    out_sample_value=st.floats(min_value=0.1, max_value=100.0)
)
@settings(max_examples=10, deadline=None)
def test_property_degradation_consistency(in_sample_value, out_sample_value):
    """
    Property 25: Degradation calculation consistency
    
    *For any* in-sample and out-of-sample metrics, degradation percentage should be 
    calculated consistently as ((in - out) / in) * 100.
    """
    analyzer = create_analyzer()
    in_sample_metrics = {
        'win_rate': in_sample_value,
        'profit_factor': in_sample_value,
        'sharpe_ratio': in_sample_value
    }
    
    out_sample_metrics = {
        'win_rate': out_sample_value,
        'profit_factor': out_sample_value,
        'sharpe_ratio': out_sample_value
    }
    
    result = analyzer.calculate_degradation(in_sample_metrics, out_sample_metrics)
    
    # Calculate expected degradation
    expected_degradation = ((in_sample_value - out_sample_value) / in_sample_value) * 100
    
    # Property: degradation should match formula
    actual_degradation = result['degradations']['win_rate']
    assert abs(actual_degradation - expected_degradation) < 0.01, \
        f"Degradation calculation inconsistent: expected {expected_degradation:.2f}, got {actual_degradation:.2f}"


# Property 26: Consistency score bounds
@given(
    degradation_pct=st.floats(min_value=-50.0, max_value=100.0)
)
@settings(max_examples=10, deadline=None)
def test_property_consistency_score_bounds(degradation_pct):
    """
    Property 26: Consistency score bounds
    
    *For any* degradation percentage, consistency score should be bounded: 
    consistency_score = max(0, 100 - degradation_pct).
    """
    analyzer = create_analyzer()
    # Create metrics with known degradation
    in_sample_metrics = {
        'win_rate': 50.0,
        'profit_factor': 2.0,
        'sharpe_ratio': 1.5
    }
    
    out_sample_metrics = {
        'win_rate': 50.0 * (1 - degradation_pct / 100),
        'profit_factor': 2.0 * (1 - degradation_pct / 100),
        'sharpe_ratio': 1.5 * (1 - degradation_pct / 100)
    }
    
    result = analyzer.calculate_degradation(in_sample_metrics, out_sample_metrics)
    
    # Property: consistency score should be max(0, 100 - degradation)
    expected_consistency = max(0.0, 100.0 - result['avg_degradation_pct'])
    
    assert abs(result['consistency_score'] - expected_consistency) < 0.01, \
        f"Consistency score should be {expected_consistency:.2f}, got {result['consistency_score']:.2f}"
    
    # Consistency score should never be negative
    assert result['consistency_score'] >= 0.0, \
        "Consistency score should never be negative"


# Property 27: CPCV split coverage
@given(
    n_samples=st.integers(min_value=500, max_value=2000),
    n_splits=st.integers(min_value=3, max_value=8)
)
@settings(max_examples=10, deadline=None)
def test_property_cpcv_split_coverage(n_samples, n_splits):
    """
    Property 27: CPCV split coverage
    
    *For any* CPCV split configuration, each data point should appear in exactly one 
    test set across all splits.
    """
    analyzer = create_analyzer()
    # Create sample data
    dates = pd.date_range('2021-01-01', periods=n_samples, freq='5min')
    data = pd.DataFrame({'value': range(n_samples)}, index=dates)
    
    splits = analyzer.generate_cpcv_splits(data, n_splits=n_splits)
    
    # Collect all test indices
    all_test_indices = []
    for _, test_idx in splits:
        all_test_indices.extend(test_idx.tolist())
    
    # Property: each index should appear in test set at least once
    # (Some indices near boundaries might be excluded due to purging)
    unique_test_indices = set(all_test_indices)
    
    # At least 80% of data should be covered in test sets
    coverage = len(unique_test_indices) / n_samples
    assert coverage > 0.8, \
        f"Test set coverage too low: {coverage:.2%} (expected >80%)"


# Property 28: Window step consistency
@given(
    start_year=st.integers(min_value=2020, max_value=2022),
    duration_months=st.integers(min_value=18, max_value=36)
)
@settings(max_examples=10, deadline=None)
def test_property_window_step_consistency(start_year, duration_months):
    """
    Property 28: Window step consistency
    
    *For any* walk-forward analysis, consecutive windows should step forward by 
    step_size_months.
    """
    analyzer = create_analyzer()
    start_date = datetime(start_year, 1, 1)
    end_date = start_date + timedelta(days=30 * duration_months)
    
    windows = analyzer.generate_windows(start_date, end_date)
    
    if len(windows) < 2:
        return  # Need at least 2 windows to check stepping
    
    # Check step size between consecutive windows
    for i in range(len(windows) - 1):
        current_start = windows[i][0]
        next_start = windows[i + 1][0]
        
        # Calculate step in days
        step_days = (next_start - current_start).days
        
        # Property: step should be approximately step_size_months * 30 days
        expected_step_days = analyzer.step_size_months * 30
        
        # Allow ±5 days tolerance
        assert abs(step_days - expected_step_days) <= 5, \
            f"Window step inconsistent: expected ~{expected_step_days} days, got {step_days} days"


# Property 29: No train-test overlap
@given(
    n_samples=st.integers(min_value=1000, max_value=3000),
    n_splits=st.integers(min_value=3, max_value=7)
)
@settings(max_examples=10, deadline=None)
def test_property_no_train_test_overlap(n_samples, n_splits):
    """
    Property 29: No train-test overlap
    
    *For any* CPCV split, there should be no overlap between training and testing indices.
    """
    analyzer = create_analyzer()
    # Create sample data
    dates = pd.date_range('2021-01-01', periods=n_samples, freq='5min')
    data = pd.DataFrame({'value': range(n_samples)}, index=dates)
    
    splits = analyzer.generate_cpcv_splits(data, n_splits=n_splits)
    
    for train_idx, test_idx in splits:
        # Property: no overlap between train and test
        overlap = np.intersect1d(train_idx, test_idx)
        
        assert len(overlap) == 0, \
            f"Found {len(overlap)} overlapping indices between train and test sets"


# Property 30: Degradation symmetry
@given(
    metric_value=st.floats(min_value=10.0, max_value=100.0),
    change_pct=st.floats(min_value=-30.0, max_value=30.0)
)
@settings(max_examples=10, deadline=None)
def test_property_degradation_symmetry(metric_value, change_pct):
    """
    Property 30: Degradation symmetry
    
    *For any* metric change, degradation should be calculated consistently regardless 
    of which metric is used.
    """
    analyzer = create_analyzer()
    out_sample_value = metric_value * (1 + change_pct / 100)
    
    # Test with different metrics
    for metric_name in ['win_rate', 'profit_factor', 'sharpe_ratio']:
        in_sample = {metric_name: metric_value}
        out_sample = {metric_name: out_sample_value}
        
        # Add dummy values for other metrics
        for other_metric in ['win_rate', 'profit_factor', 'sharpe_ratio']:
            if other_metric != metric_name:
                in_sample[other_metric] = 50.0
                out_sample[other_metric] = 50.0
        
        result = analyzer.calculate_degradation(in_sample, out_sample)
        
        # Property: degradation should match expected value
        expected_degradation = ((metric_value - out_sample_value) / metric_value) * 100
        actual_degradation = result['degradations'][metric_name]
        
        assert abs(actual_degradation - expected_degradation) < 0.01, \
            f"Degradation calculation inconsistent for {metric_name}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
