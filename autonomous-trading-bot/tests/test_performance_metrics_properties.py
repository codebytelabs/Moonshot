"""
Property-based tests for Performance Metrics Calculator.

Tests universal properties that should hold for all valid inputs.
Uses hypothesis library for property-based testing.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.performance_metrics_calculator import PerformanceMetricsCalculator, PerformanceMetrics


# Strategy for generating valid trade data
@st.composite
def trade_data(draw):
    """Generate valid trade data for testing."""
    num_trades = draw(st.integers(min_value=1, max_value=100))
    
    trades = []
    for i in range(num_trades):
        pnl = draw(st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False))
        r_multiple = draw(st.floats(min_value=-5, max_value=20, allow_nan=False, allow_infinity=False))
        
        trades.append({
            'pnl': pnl,
            'r_multiple': r_multiple,
            'symbol': 'BTC/USDT',
            'entry_price': 50000.0,
            'exit_price': 50000.0 + pnl,
            'quantity': 0.1
        })
    
    return trades


@st.composite
def equity_curve_data(draw):
    """Generate valid equity curve for testing."""
    num_points = draw(st.integers(min_value=10, max_value=500))
    initial_equity = draw(st.floats(min_value=10000, max_value=1000000))
    
    # Generate equity values with random walk
    equity_values = [initial_equity]
    for _ in range(num_points - 1):
        change_pct = draw(st.floats(min_value=-0.05, max_value=0.05))
        new_equity = equity_values[-1] * (1 + change_pct)
        equity_values.append(max(1000, new_equity))  # Ensure positive
    
    # Create time index
    start_date = datetime(2021, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(num_points)]
    
    return pd.Series(equity_values, index=dates)


class TestPerformanceMetricsProperties:
    """Property-based tests for performance metrics calculations."""
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_15_win_rate_bounds(self, trades):
        """
        **Property 15: Win rate calculation**
        **Validates: Requirement 8.1**
        
        Property: Win rate must be between 0% and 100% inclusive.
        """
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        win_rate = calculator.win_rate()
        
        assert 0.0 <= win_rate <= 100.0, f"Win rate {win_rate} outside valid range [0, 100]"
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_15_win_rate_accuracy(self, trades):
        """
        **Property 15: Win rate calculation accuracy**
        **Validates: Requirement 8.1**
        
        Property: Win rate should equal (winning_trades / total_trades) * 100.
        """
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        win_rate = calculator.win_rate()
        
        # Calculate expected win rate
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        expected_win_rate = (winning_trades / len(trades)) * 100
        
        assert abs(win_rate - expected_win_rate) < 0.01, \
            f"Win rate {win_rate} doesn't match expected {expected_win_rate}"
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_16_profit_factor_positive(self, trades):
        """
        **Property 16: Profit factor calculation**
        **Validates: Requirement 8.2**
        
        Property: Profit factor must be non-negative.
        If there are profits and no losses, profit factor should be infinity.
        """
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        profit_factor = calculator.profit_factor()
        
        assert profit_factor >= 0.0 or profit_factor == float('inf'), \
            f"Profit factor {profit_factor} is negative"
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_16_profit_factor_formula(self, trades):
        """
        **Property 16: Profit factor formula validation**
        **Validates: Requirement 8.2**
        
        Property: Profit factor = gross_profits / gross_losses.
        """
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        profit_factor = calculator.profit_factor()
        
        # Calculate expected profit factor
        gross_profits = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_losses = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        
        if gross_losses == 0:
            if gross_profits > 0:
                assert profit_factor == float('inf'), "Should be infinity when no losses but profits exist"
            else:
                assert profit_factor == 0.0, "Should be 0 when no profits and no losses"
        else:
            expected_pf = gross_profits / gross_losses
            assert abs(profit_factor - expected_pf) < 0.01, \
                f"Profit factor {profit_factor} doesn't match expected {expected_pf}"
    
    @given(equity_curve_data())
    @settings(max_examples=10, deadline=None)
    def test_property_17_sharpe_ratio_finite(self, equity_curve):
        """
        **Property 17: Sharpe ratio calculation**
        **Validates: Requirement 8.3**
        
        Property: Sharpe ratio must be finite (not NaN or infinity) for valid equity curves.
        """
        # Create dummy trades
        trades = [{'pnl': 100, 'r_multiple': 1.5}]
        
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        sharpe = calculator.sharpe_ratio()
        
        assert not np.isnan(sharpe), "Sharpe ratio is NaN"
        assert not np.isinf(sharpe), "Sharpe ratio is infinite"
    
    @given(equity_curve_data())
    @settings(max_examples=10, deadline=None)
    def test_property_17_sharpe_ratio_sign(self, equity_curve):
        """
        **Property 17: Sharpe ratio sign consistency**
        **Validates: Requirement 8.3**
        
        Property: Positive average returns should give positive Sharpe ratio.
        """
        # Ensure positive returns by making equity curve monotonically increasing
        equity_values = equity_curve.values.copy()  # Make a copy to avoid read-only error
        for i in range(1, len(equity_values)):
            if equity_values[i] < equity_values[i-1]:
                equity_values[i] = equity_values[i-1] * 1.001  # Small positive return
        
        equity_curve = pd.Series(equity_values, index=equity_curve.index)
        
        trades = [{'pnl': 100, 'r_multiple': 1.5}]
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        sharpe = calculator.sharpe_ratio()
        
        # With consistently positive returns, Sharpe should be positive
        assert sharpe >= 0, f"Sharpe ratio {sharpe} is negative despite positive returns"
    
    @given(equity_curve_data())
    @settings(max_examples=10, deadline=None)
    def test_property_18_max_drawdown_bounds(self, equity_curve):
        """
        **Property 18: Maximum drawdown calculation**
        **Validates: Requirement 8.4**
        
        Property: Maximum drawdown must be between 0% and 100%.
        """
        trades = [{'pnl': 100, 'r_multiple': 1.5}]
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        max_dd = calculator.max_drawdown()
        
        assert 0.0 <= max_dd <= 100.0, f"Max drawdown {max_dd} outside valid range [0, 100]"
    
    @given(equity_curve_data())
    @settings(max_examples=10, deadline=None)
    def test_property_18_max_drawdown_monotonic_equity(self, equity_curve):
        """
        **Property 18: Maximum drawdown for monotonic equity**
        **Validates: Requirement 8.4**
        
        Property: If equity curve is monotonically increasing, max drawdown should be ~0%.
        """
        # Make equity curve strictly increasing
        equity_values = sorted(equity_curve.values)
        equity_curve = pd.Series(equity_values, index=equity_curve.index)
        
        trades = [{'pnl': 100, 'r_multiple': 1.5}]
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        max_dd = calculator.max_drawdown()
        
        # Should be very close to 0 for monotonic increasing
        assert max_dd < 1.0, f"Max drawdown {max_dd} too high for monotonic equity curve"
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_19_r_multiple_average(self, trades):
        """
        **Property 19: R-multiple calculation**
        **Validates: Requirement 8.5**
        
        Property: Average R-multiple should equal mean of all trade R-multiples.
        """
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        avg_r = calculator.avg_r_multiple()
        
        # Calculate expected average
        r_multiples = [t['r_multiple'] for t in trades]
        expected_avg = np.mean(r_multiples)
        
        assert abs(avg_r - expected_avg) < 0.01, \
            f"Average R-multiple {avg_r} doesn't match expected {expected_avg}"
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_19_r_multiple_distribution_sum(self, trades):
        """
        **Property 19: R-multiple distribution completeness**
        **Validates: Requirement 8.5, 8.7**
        
        Property: Sum of all R-multiple distribution buckets should equal total trades.
        """
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        distribution = calculator.r_multiple_distribution()
        
        total_in_buckets = sum(distribution.values())
        
        assert total_in_buckets == len(trades), \
            f"Distribution sum {total_in_buckets} doesn't match total trades {len(trades)}"
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_20_expectancy_formula(self, trades):
        """
        **Property 20: Expectancy calculation**
        **Validates: Requirement 8.6**
        
        Property: Expectancy = (win_rate × avg_win) - (loss_rate × avg_loss).
        """
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        expectancy = calculator.expectancy()
        
        # Calculate expected expectancy
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        if len(winning_trades) == 0 and len(losing_trades) == 0:
            assert expectancy == 0.0, "Expectancy should be 0 when no winning or losing trades"
        else:
            win_rate = len(winning_trades) / len(trades)
            loss_rate = len(losing_trades) / len(trades)
            
            avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0.0
            avg_loss = abs(np.mean([t['pnl'] for t in losing_trades])) if losing_trades else 0.0
            
            expected_exp = (win_rate * avg_win) - (loss_rate * avg_loss)
            
            assert abs(expectancy - expected_exp) < 0.01, \
                f"Expectancy {expectancy} doesn't match expected {expected_exp}"
    
    @given(trade_data())
    @settings(max_examples=10, deadline=None)
    def test_property_20_expectancy_sign_consistency(self, trades):
        """
        **Property 20: Expectancy sign consistency**
        **Validates: Requirement 8.6**
        
        Property: If all trades are profitable, expectancy should be positive.
        """
        # Make all trades profitable
        for trade in trades:
            trade['pnl'] = abs(trade['pnl']) + 1  # Ensure positive
        
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        
        expectancy = calculator.expectancy()
        
        assert expectancy > 0, f"Expectancy {expectancy} should be positive when all trades win"
    
    def test_property_metrics_with_no_trades(self):
        """
        Property: Calculator should handle empty trade list gracefully.
        """
        trades = []
        equity_curve = pd.Series([100000] * 10, index=pd.date_range('2021-01-01', periods=10))
        
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        metrics = calculator.calculate_all_metrics()
        
        assert metrics.win_rate == 0.0
        assert metrics.profit_factor == 0.0
        assert metrics.expectancy == 0.0
        assert metrics.total_trades == 0
    
    def test_property_metrics_validation_targets(self):
        """
        Property: Validation targets should correctly identify good/bad metrics.
        **Validates: Requirement 8.9**
        """
        # Create good metrics
        trades = [
            {'pnl': 100, 'r_multiple': 2.0},
            {'pnl': 150, 'r_multiple': 3.0},
            {'pnl': -30, 'r_multiple': -0.5},
        ]
        
        equity_curve = pd.Series(
            [100000, 100100, 100250, 100220],
            index=pd.date_range('2021-01-01', periods=4)
        )
        
        calculator = PerformanceMetricsCalculator(trades, equity_curve)
        metrics = calculator.calculate_all_metrics()
        
        validation = metrics.validate_targets()
        
        # Win rate should be 66.7% (2/3) - passes >50% target
        assert validation['win_rate_ok'] == True
        
        # Profit factor should be 250/30 = 8.33 - passes >2.0 target
        assert validation['profit_factor_ok'] == True
        
        # Max drawdown should be small - passes <20% target
        assert validation['max_drawdown_ok'] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
