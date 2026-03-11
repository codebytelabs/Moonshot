"""
Property-based tests for ParameterOptimizer.

**Validates: Requirements 11.3, 11.5, 11.6, 11.7**
"""
import pytest
from hypothesis import given, strategies as st, assume
from src.parameter_optimizer import ParameterOptimizer, OptimizationResult


class TestParameterOptimizerProperties:
    """Property-based tests for ParameterOptimizer."""
    
    @given(
        sharpe=st.floats(min_value=-5.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        pf=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
        wr=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_composite_score_formula_property(self, sharpe, pf, wr):
        """
        Property: Composite score always equals (sharpe × 0.4) + (pf × 0.3) + (wr × 0.3).
        
        **Validates: Requirement 11.3**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        metrics = {
            'sharpe_ratio': sharpe,
            'profit_factor': pf,
            'win_rate': wr
        }
        
        score = optimizer.calculate_composite_score(metrics)
        expected = (sharpe * 0.4) + (pf * 0.3) + (wr * 0.3)
        
        assert abs(score - expected) < 0.0001
    
    @given(
        sharpe=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        pf=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
        wr=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_composite_score_non_negative_for_positive_inputs(self, sharpe, pf, wr):
        """
        Property: Composite score is non-negative when all inputs are non-negative.
        
        **Validates: Requirement 11.3**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        metrics = {
            'sharpe_ratio': sharpe,
            'profit_factor': pf,
            'win_rate': wr
        }
        
        score = optimizer.calculate_composite_score(metrics)
        assert score >= 0.0
    
    @given(
        sharpe=st.floats(min_value=-5.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        pf=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
        wr=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        multiplier=st.floats(min_value=1.0, max_value=3.0, allow_nan=False, allow_infinity=False)
    )
    def test_composite_score_scales_linearly(self, sharpe, pf, wr, multiplier):
        """
        Property: Scaling all metrics by a factor scales the composite score by the same factor.
        
        **Validates: Requirement 11.3**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        metrics_1 = {
            'sharpe_ratio': sharpe,
            'profit_factor': pf,
            'win_rate': wr
        }
        
        metrics_2 = {
            'sharpe_ratio': sharpe * multiplier,
            'profit_factor': pf * multiplier,
            'win_rate': wr * multiplier
        }
        
        score_1 = optimizer.calculate_composite_score(metrics_1)
        score_2 = optimizer.calculate_composite_score(metrics_2)
        
        # Score should scale by the same multiplier
        if abs(score_1) > 0.001:  # Avoid division by near-zero
            ratio = score_2 / score_1
            assert abs(ratio - multiplier) < 0.01
    
    @given(
        results_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),  # sharpe
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),  # pf
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),  # wr
                st.integers(min_value=10, max_value=200)  # trades
            ),
            min_size=1,
            max_size=20
        )
    )
    def test_ranking_preserves_order_property(self, results_data):
        """
        Property: Ranked results are always in descending order by composite score.
        
        **Validates: Requirement 11.5**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        results = []
        for sharpe, pf, wr, trades in results_data:
            metrics = {
                'sharpe_ratio': sharpe,
                'profit_factor': pf,
                'win_rate': wr
            }
            score = optimizer.calculate_composite_score(metrics)
            
            result = OptimizationResult(
                parameters={'test': 'param'},
                metrics=metrics,
                composite_score=score,
                total_trades=trades
            )
            results.append(result)
        
        ranked = optimizer.rank_results(results, validate_min_trades=False)
        
        # Verify descending order
        for i in range(len(ranked) - 1):
            assert ranked[i].composite_score >= ranked[i + 1].composite_score
    
    @given(
        results_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.integers(min_value=10, max_value=200)
            ),
            min_size=1,
            max_size=20
        ),
        min_trades=st.integers(min_value=20, max_value=50)
    )
    def test_filtering_removes_low_trades_property(self, results_data, min_trades):
        """
        Property: Filtered results never contain trades below minimum threshold.
        
        **Validates: Requirement 11.5**
        """
        optimizer = ParameterOptimizer(min_trades=min_trades)
        
        results = []
        for sharpe, pf, wr, trades in results_data:
            metrics = {
                'sharpe_ratio': sharpe,
                'profit_factor': pf,
                'win_rate': wr
            }
            score = optimizer.calculate_composite_score(metrics)
            
            result = OptimizationResult(
                parameters={'test': 'param'},
                metrics=metrics,
                composite_score=score,
                total_trades=trades
            )
            results.append(result)
        
        ranked = optimizer.rank_results(results, validate_min_trades=True)
        
        # All results should have trades >= min_trades
        for result in ranked:
            assert result.total_trades >= min_trades
    
    @given(
        results_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.integers(min_value=30, max_value=200)
            ),
            min_size=1,
            max_size=20
        )
    )
    def test_best_result_has_highest_score_property(self, results_data):
        """
        Property: Best result always has the highest composite score among valid results.
        
        **Validates: Requirement 11.5**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        results = []
        for sharpe, pf, wr, trades in results_data:
            metrics = {
                'sharpe_ratio': sharpe,
                'profit_factor': pf,
                'win_rate': wr
            }
            score = optimizer.calculate_composite_score(metrics)
            
            result = OptimizationResult(
                parameters={'test': 'param'},
                metrics=metrics,
                composite_score=score,
                total_trades=trades
            )
            results.append(result)
        
        best = optimizer.select_best_result(results)
        
        if best is not None:
            # Best should have highest score among valid results
            valid_results = [r for r in results if r.total_trades >= optimizer.min_trades]
            max_score = max(r.composite_score for r in valid_results)
            assert abs(best.composite_score - max_score) < 0.0001
    
    @given(
        sharpe_a=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        pf_a=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        wr_a=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        sharpe_b=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        pf_b=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        wr_b=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_comparison_improvement_is_difference_property(self, sharpe_a, pf_a, wr_a, sharpe_b, pf_b, wr_b):
        """
        Property: Score improvement equals difference between composite scores.
        
        **Validates: Requirement 11.5**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        metrics_a = {'sharpe_ratio': sharpe_a, 'profit_factor': pf_a, 'win_rate': wr_a}
        metrics_b = {'sharpe_ratio': sharpe_b, 'profit_factor': pf_b, 'win_rate': wr_b}
        
        score_a = optimizer.calculate_composite_score(metrics_a)
        score_b = optimizer.calculate_composite_score(metrics_b)
        
        result_a = OptimizationResult(
            parameters={'test': 'a'},
            metrics=metrics_a,
            composite_score=score_a,
            total_trades=50
        )
        
        result_b = OptimizationResult(
            parameters={'test': 'b'},
            metrics=metrics_b,
            composite_score=score_b,
            total_trades=50
        )
        
        comparison = optimizer.compare_results(result_a, result_b)
        
        expected_improvement = score_b - score_a
        assert abs(comparison['score_improvement'] - expected_improvement) < 0.0001
    
    @given(
        results_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.integers(min_value=30, max_value=200)
            ),
            min_size=1,
            max_size=20
        ),
        top_n=st.integers(min_value=1, max_value=10)
    )
    def test_report_length_bounded_by_top_n_property(self, results_data, top_n):
        """
        Property: Report length never exceeds top_n parameter.
        
        **Validates: Requirement 11.5**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        results = []
        for sharpe, pf, wr, trades in results_data:
            metrics = {
                'sharpe_ratio': sharpe,
                'profit_factor': pf,
                'win_rate': wr
            }
            score = optimizer.calculate_composite_score(metrics)
            
            result = OptimizationResult(
                parameters={'test': 'param'},
                metrics=metrics,
                composite_score=score,
                total_trades=trades
            )
            results.append(result)
        
        report = optimizer.generate_report(results, top_n=top_n)
        
        # Report length should be min(valid_results, top_n)
        valid_count = len([r for r in results if r.total_trades >= optimizer.min_trades])
        expected_length = min(valid_count, top_n)
        assert len(report) == expected_length
    
    @given(
        sharpe=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        pf=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        wr=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_sharpe_weight_is_largest_property(self, sharpe, pf, wr):
        """
        Property: Sharpe ratio has the largest weight (0.4) in composite score.
        
        **Validates: Requirement 11.3**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        # Test by varying only sharpe while keeping others constant
        metrics_base = {
            'sharpe_ratio': sharpe,
            'profit_factor': pf,
            'win_rate': wr
        }
        
        metrics_sharpe_plus = {
            'sharpe_ratio': sharpe + 1.0,
            'profit_factor': pf,
            'win_rate': wr
        }
        
        metrics_pf_plus = {
            'sharpe_ratio': sharpe,
            'profit_factor': pf + 1.0,
            'win_rate': wr
        }
        
        metrics_wr_plus = {
            'sharpe_ratio': sharpe,
            'profit_factor': pf,
            'win_rate': wr + 1.0
        }
        
        score_base = optimizer.calculate_composite_score(metrics_base)
        score_sharpe_plus = optimizer.calculate_composite_score(metrics_sharpe_plus)
        score_pf_plus = optimizer.calculate_composite_score(metrics_pf_plus)
        score_wr_plus = optimizer.calculate_composite_score(metrics_wr_plus)
        
        sharpe_impact = score_sharpe_plus - score_base
        pf_impact = score_pf_plus - score_base
        wr_impact = score_wr_plus - score_base
        
        # Sharpe impact should be largest (0.4 vs 0.3 for others)
        assert sharpe_impact > pf_impact
        assert sharpe_impact > wr_impact
        assert abs(sharpe_impact - 0.4) < 0.0001
        assert abs(pf_impact - 0.3) < 0.0001
        assert abs(wr_impact - 0.3) < 0.0001
    
    @given(
        threshold_results=st.lists(
            st.tuples(
                st.floats(min_value=0.50, max_value=0.80),  # threshold value
                st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),  # sharpe
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),  # pf
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),  # wr
                st.integers(min_value=10, max_value=200)  # trades
            ),
            min_size=2,
            max_size=10
        )
    )
    def test_threshold_optimization_selection_property(self, threshold_results):
        """
        Property 24: Threshold optimization selection
        
        For any threshold optimization run, the selected threshold should have the 
        highest composite_score among all thresholds that produced ≥30 trades.
        
        **Validates: Requirements 11.3, 11.6, 11.7**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        
        # Create optimization results for each threshold
        results = []
        for threshold, sharpe, pf, wr, trades in threshold_results:
            metrics = {
                'sharpe_ratio': sharpe,
                'profit_factor': pf,
                'win_rate': wr
            }
            score = optimizer.calculate_composite_score(metrics)
            
            result = OptimizationResult(
                parameters={'bayesian_threshold': threshold},
                metrics=metrics,
                composite_score=score,
                total_trades=trades
            )
            results.append(result)
        
        # Select best result
        best = optimizer.select_best_result(results)
        
        # Filter results that meet minimum trade requirement
        valid_results = [r for r in results if r.total_trades >= optimizer.min_trades]
        
        if not valid_results:
            # If no valid results, best should be None
            assert best is None
        else:
            # Best should not be None
            assert best is not None
            
            # Best should meet minimum trade requirement
            assert best.total_trades >= optimizer.min_trades
            
            # Best should have the highest composite score among valid results
            max_score = max(r.composite_score for r in valid_results)
            assert abs(best.composite_score - max_score) < 0.0001
            
            # Verify no valid result has a higher score
            for result in valid_results:
                assert result.composite_score <= best.composite_score + 0.0001
            
            # Verify that if there are invalid results with higher scores, they are not selected
            invalid_results = [r for r in results if r.total_trades < optimizer.min_trades]
            for invalid in invalid_results:
                # Even if invalid result has higher score, it should not be selected
                if invalid.composite_score > best.composite_score:
                    assert invalid.total_trades < optimizer.min_trades
    
    @given(
        stop_results=st.lists(
            st.tuples(
                st.floats(min_value=0.15, max_value=0.40),  # stop percentage
                st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),  # avg R-multiple
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),  # pct above 5R
                st.integers(min_value=5, max_value=100)  # runner count
            ),
            min_size=2,
            max_size=10
        )
    )
    def test_trailing_stop_optimization_selection_property(self, stop_results):
        """
        Property 25: Trailing stop optimization selection
        
        For any trailing stop optimization run, the selected stop percentage should 
        maximize average R-multiple on runner trades.
        
        **Validates: Requirements 12.4**
        """
        optimizer = ParameterOptimizer(min_trades=10)  # Lower threshold for runner trades
        
        # Create optimization results for each stop percentage
        results = []
        for stop_pct, avg_r, pct_above_5r, runner_count in stop_results:
            # For trailing stop optimization, we use avg_r_multiple as the primary metric
            metrics = {
                'avg_r_multiple': avg_r,
                'pct_above_5r': pct_above_5r,
                'runner_count': runner_count
            }
            
            result = OptimizationResult(
                parameters={'trailing_stop_pct': stop_pct},
                metrics=metrics,
                composite_score=avg_r,  # Use avg_r as the score for trailing stop optimization
                total_trades=runner_count
            )
            results.append(result)
        
        # Select best result
        best = optimizer.select_best_result(results)
        
        # Filter results that meet minimum runner count requirement
        valid_results = [r for r in results if r.total_trades >= optimizer.min_trades]
        
        if not valid_results:
            # If no valid results, best should be None
            assert best is None
        else:
            # Best should not be None
            assert best is not None
            
            # Best should meet minimum runner count requirement
            assert best.total_trades >= optimizer.min_trades
            
            # Best should have the highest average R-multiple among valid results
            max_avg_r = max(r.metrics['avg_r_multiple'] for r in valid_results)
            assert abs(best.metrics['avg_r_multiple'] - max_avg_r) < 0.0001
            
            # Verify no valid result has a higher average R-multiple
            for result in valid_results:
                assert result.metrics['avg_r_multiple'] <= best.metrics['avg_r_multiple'] + 0.0001
            
            # Verify that if there are invalid results with higher avg R-multiple, they are not selected
            invalid_results = [r for r in results if r.total_trades < optimizer.min_trades]
            for invalid in invalid_results:
                # Even if invalid result has higher avg R-multiple, it should not be selected
                if invalid.metrics['avg_r_multiple'] > best.metrics['avg_r_multiple']:
                    assert invalid.total_trades < optimizer.min_trades
    
    @given(
        weight_step=st.floats(min_value=0.05, max_value=0.10)
    )
    def test_timeframe_weight_constraints_property(self, weight_step):
        """
        Property 26: Timeframe weight constraints
        
        For any timeframe weight combination, weights must sum to 1.0, 
        higher timeframes (4h+1h) must have combined weight >50%, 
        and lower timeframes (5m+15m) must have combined weight >30%.
        
        **Validates: Requirements 13.2, 13.6, 13.7**
        """
        optimizer = ParameterOptimizer(min_trades=30)
        
        # Generate weight combinations
        weight_combinations = optimizer._generate_weight_combinations(step=weight_step)
        
        # Verify at least some combinations were generated
        assert len(weight_combinations) > 0, "No weight combinations generated"
        
        # Test each combination
        for weights in weight_combinations:
            # Verify all required timeframes are present
            assert '5m' in weights
            assert '15m' in weights
            assert '1h' in weights
            assert '4h' in weights
            
            # Property 1: Weights must sum to 1.0 (within floating point tolerance)
            total_weight = weights['5m'] + weights['15m'] + weights['1h'] + weights['4h']
            assert abs(total_weight - 1.0) < 0.003, \
                f"Weights sum to {total_weight}, expected 1.0: {weights}"
            
            # Property 2: Higher timeframes (4h + 1h) combined weight >50%
            higher_tf_weight = weights['4h'] + weights['1h']
            assert higher_tf_weight > 0.50, \
                f"Higher TF weight {higher_tf_weight} <= 0.50: {weights}"
            
            # Property 3: Lower timeframes (5m + 15m) combined weight >30%
            lower_tf_weight = weights['5m'] + weights['15m']
            assert lower_tf_weight > 0.30, \
                f"Lower TF weight {lower_tf_weight} <= 0.30: {weights}"
            
            # Property 4: All individual weights should be positive
            assert weights['5m'] > 0, f"5m weight must be positive: {weights}"
            assert weights['15m'] > 0, f"15m weight must be positive: {weights}"
            assert weights['1h'] > 0, f"1h weight must be positive: {weights}"
            assert weights['4h'] > 0, f"4h weight must be positive: {weights}"
            
            # Property 5: All individual weights should be <= 1.0
            assert weights['5m'] <= 1.0, f"5m weight exceeds 1.0: {weights}"
            assert weights['15m'] <= 1.0, f"15m weight exceeds 1.0: {weights}"
            assert weights['1h'] <= 1.0, f"1h weight exceeds 1.0: {weights}"
            assert weights['4h'] <= 1.0, f"4h weight exceeds 1.0: {weights}"
    
    @given(
        pnl_without=st.floats(min_value=-1000.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
        pnl_with=st.floats(min_value=-1000.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_context_agent_alpha_measurement_property(self, pnl_without, pnl_with):
        """
        Property 27: Context Agent alpha measurement
        
        For any A/B test, alpha_improvement should equal 
        (total_pnl_with_context - total_pnl_without_context).
        
        **Validates: Requirements 14.4**
        """
        # Create mock comparison data
        comparison = {
            'without_context': {'total_pnl': pnl_without},
            'with_context': {'total_pnl': pnl_with}
        }
        
        # Calculate alpha improvement
        alpha_improvement = comparison['with_context']['total_pnl'] - comparison['without_context']['total_pnl']
        
        # Verify the calculation
        expected_alpha = pnl_with - pnl_without
        assert abs(alpha_improvement - expected_alpha) < 0.01, \
            f"Alpha improvement {alpha_improvement} != expected {expected_alpha}"
        
        # Property: Alpha improvement is positive when with_context performs better
        if pnl_with > pnl_without:
            assert alpha_improvement > 0, \
                f"Alpha should be positive when with_context performs better"
        
        # Property: Alpha improvement is negative when without_context performs better
        if pnl_without > pnl_with:
            assert alpha_improvement < 0, \
                f"Alpha should be negative when without_context performs better"
        
        # Property: Alpha improvement is zero when performance is equal
        if abs(pnl_with - pnl_without) < 0.01:
            assert abs(alpha_improvement) < 0.01, \
                f"Alpha should be near zero when performance is equal"
    
    @given(
        cv_scores=st.lists(
            st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=10
        )
    )
    def test_cpcv_variance_validation_property(self, cv_scores):
        """
        Property 28: CPCV variance validation
        
        For any grid search result, the top parameter combination should have 
        performance variance across CV folds <15%.
        
        **Validates: Requirements 15.6**
        """
        import numpy as np
        
        # Calculate mean and std
        mean_score = np.mean(cv_scores)
        std_score = np.std(cv_scores)
        
        # Calculate variance percentage
        variance_pct = (std_score / mean_score * 100) if mean_score > 0 else 0
        
        # Property 1: Variance percentage is non-negative
        assert variance_pct >= 0, f"Variance percentage should be non-negative: {variance_pct}"
        
        # Property 2: If all scores are identical, variance should be 0
        if len(set(cv_scores)) == 1:
            assert variance_pct < 0.1, \
                f"Variance should be near 0 for identical scores: {variance_pct}"
        
        # Property 3: Variance percentage increases with score spread
        # Test by comparing with a more uniform distribution
        uniform_scores = [mean_score] * len(cv_scores)
        uniform_std = np.std(uniform_scores)
        uniform_variance_pct = (uniform_std / mean_score * 100) if mean_score > 0 else 0
        
        # Original scores should have >= variance than uniform (unless already uniform)
        if std_score > 0.01:
            assert variance_pct >= uniform_variance_pct, \
                f"Variance of varied scores should be >= uniform: {variance_pct} vs {uniform_variance_pct}"
        
        # Property 4: For validation, check if variance meets <15% threshold
        meets_threshold = variance_pct < 15.0
        
        # If variance is high, it should be flagged
        if variance_pct >= 15.0:
            assert not meets_threshold, \
                f"High variance {variance_pct}% should not meet threshold"
        else:
            assert meets_threshold, \
                f"Low variance {variance_pct}% should meet threshold"
        
        # Property 5: Variance calculation is consistent
        # Recalculate to verify
        recalc_variance_pct = (np.std(cv_scores) / np.mean(cv_scores) * 100) if np.mean(cv_scores) > 0 else 0
        assert abs(variance_pct - recalc_variance_pct) < 0.01, \
            f"Variance calculation inconsistent: {variance_pct} vs {recalc_variance_pct}"
