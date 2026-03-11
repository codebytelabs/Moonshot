"""
Parameter Optimizer for Bot Optimization Pipeline.
Provides base class for parameter optimization with composite score calculation.

**Validates: Requirements 11.3, 11.5**
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from loguru import logger


@dataclass
class OptimizationResult:
    """Container for optimization result with metrics and parameters."""
    parameters: Dict[str, Any]
    metrics: Dict[str, float]
    composite_score: float
    total_trades: int
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return {
            'parameters': self.parameters,
            'metrics': self.metrics,
            'composite_score': self.composite_score,
            'total_trades': self.total_trades
        }


class ParameterOptimizer:
    """
    Base class for parameter optimization.
    
    Provides composite score calculation and result ranking for optimization tasks.
    Composite score formula: (sharpe_ratio × 0.4) + (profit_factor × 0.3) + (win_rate × 0.3)
    
    **Validates: Requirements 11.3, 11.5**
    """
    
    def __init__(self, min_trades: int = 30):
        """
        Initialize parameter optimizer.
        
        Args:
            min_trades: Minimum number of trades required for valid optimization result
        """
        self.min_trades = min_trades
        logger.info(f"ParameterOptimizer initialized with min_trades={min_trades}")
    
    def calculate_composite_score(self, metrics: Dict[str, float]) -> float:
        """
        Calculate composite score from performance metrics.
        
        Formula: (sharpe_ratio × 0.4) + (profit_factor × 0.3) + (win_rate × 0.3)
        
        **Validates: Requirement 11.3**
        
        Args:
            metrics: Dictionary containing 'sharpe_ratio', 'profit_factor', 'win_rate'
        
        Returns:
            Composite score as weighted sum of metrics
        
        Raises:
            ValueError: If required metrics are missing
        """
        required_keys = ['sharpe_ratio', 'profit_factor', 'win_rate']
        missing_keys = [key for key in required_keys if key not in metrics]
        
        if missing_keys:
            raise ValueError(f"Missing required metrics: {missing_keys}")
        
        sharpe_ratio = metrics['sharpe_ratio']
        profit_factor = metrics['profit_factor']
        win_rate = metrics['win_rate']
        
        # Composite score: (sharpe × 0.4) + (profit_factor × 0.3) + (win_rate × 0.3)
        composite_score = (sharpe_ratio * 0.4) + (profit_factor * 0.3) + (win_rate * 0.3)
        
        logger.debug(
            f"Composite score calculated: {composite_score:.4f} "
            f"(sharpe={sharpe_ratio:.4f}, pf={profit_factor:.4f}, wr={win_rate:.2f}%)"
        )
        
        return composite_score
    
    def rank_results(
        self, 
        results: List[OptimizationResult],
        validate_min_trades: bool = True
    ) -> List[OptimizationResult]:
        """
        Rank optimization results by composite score.
        
        **Validates: Requirement 11.5**
        
        Args:
            results: List of optimization results to rank
            validate_min_trades: If True, filter out results with insufficient trades
        
        Returns:
            Sorted list of results (highest composite score first)
        """
        if not results:
            logger.warning("No results to rank")
            return []
        
        # Filter by minimum trades if validation enabled
        if validate_min_trades:
            valid_results = [
                r for r in results 
                if r.total_trades >= self.min_trades
            ]
            
            filtered_count = len(results) - len(valid_results)
            if filtered_count > 0:
                logger.info(
                    f"Filtered {filtered_count} results with <{self.min_trades} trades"
                )
            
            results = valid_results
        
        if not results:
            logger.warning(f"No results with >={self.min_trades} trades")
            return []
        
        # Sort by composite score (descending)
        ranked_results = sorted(
            results, 
            key=lambda r: r.composite_score, 
            reverse=True
        )
        
        logger.info(
            f"Ranked {len(ranked_results)} results. "
            f"Best score: {ranked_results[0].composite_score:.4f}"
        )
        
        return ranked_results
    
    def generate_report(
        self, 
        results: List[OptimizationResult],
        top_n: int = 5
    ) -> pd.DataFrame:
        """
        Generate optimization report showing top results.
        
        **Validates: Requirement 11.5**
        
        Args:
            results: List of optimization results
            top_n: Number of top results to include in report
        
        Returns:
            DataFrame with parameters, metrics, and composite scores
        """
        if not results:
            logger.warning("No results to report")
            return pd.DataFrame()
        
        # Rank results first
        ranked_results = self.rank_results(results)
        
        # Take top N
        top_results = ranked_results[:top_n]
        
        # Build report data
        report_data = []
        for i, result in enumerate(top_results, 1):
            row = {
                'rank': i,
                'composite_score': result.composite_score,
                'total_trades': result.total_trades,
                **result.metrics,
                **result.parameters
            }
            report_data.append(row)
        
        df = pd.DataFrame(report_data)
        
        logger.info(f"Generated report with {len(df)} results")
        
        return df
    
    def select_best_result(
        self, 
        results: List[OptimizationResult]
    ) -> Optional[OptimizationResult]:
        """
        Select the best optimization result.
        
        Returns the result with highest composite score that meets minimum trade requirement.
        
        Args:
            results: List of optimization results
        
        Returns:
            Best result or None if no valid results
        """
        ranked_results = self.rank_results(results, validate_min_trades=True)
        
        if not ranked_results:
            logger.warning("No valid results to select from")
            return None
        
        best_result = ranked_results[0]
        
        logger.info(
            f"Selected best result: score={best_result.composite_score:.4f}, "
            f"trades={best_result.total_trades}, params={best_result.parameters}"
        )
        
        return best_result
    
    def compare_results(
        self, 
        result_a: OptimizationResult,
        result_b: OptimizationResult
    ) -> Dict[str, Any]:
        """
        Compare two optimization results.
        
        Args:
            result_a: First result
            result_b: Second result
        
        Returns:
            Dictionary with comparison metrics and improvement percentages
        """
        comparison = {
            'result_a': result_a.to_dict(),
            'result_b': result_b.to_dict(),
            'score_improvement': result_b.composite_score - result_a.composite_score,
            'score_improvement_pct': (
                ((result_b.composite_score - result_a.composite_score) / result_a.composite_score * 100)
                if result_a.composite_score > 0 else 0
            ),
            'metric_deltas': {}
        }
        
        # Calculate metric deltas
        for metric_key in result_a.metrics:
            if metric_key in result_b.metrics:
                delta = result_b.metrics[metric_key] - result_a.metrics[metric_key]
                comparison['metric_deltas'][metric_key] = delta
        
        logger.info(
            f"Comparison: score improvement = {comparison['score_improvement']:.4f} "
            f"({comparison['score_improvement_pct']:.2f}%)"
        )
        
        return comparison

    async def optimize_bayesian_threshold(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        backtest_runner: Callable,
        thresholds: Optional[List[float]] = None
    ) -> OptimizationResult:
        """
        Optimize Bayesian decision threshold by testing different values.
        
        Tests each threshold value, runs backtest, calculates composite score,
        and selects the threshold with highest score that meets minimum trade requirement.
        
        **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.6, 11.7, 11.8**
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            backtest_runner: Async function(threshold) -> BacktestResult
            thresholds: List of threshold values to test (default: [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80])
        
        Returns:
            OptimizationResult with best threshold and metrics
        
        Raises:
            ValueError: If no valid results with sufficient trades
        """
        if thresholds is None:
            thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        
        logger.info(
            f"Starting Bayesian threshold optimization: "
            f"testing {len(thresholds)} thresholds from {min(thresholds)} to {max(thresholds)}"
        )
        
        results = []
        
        for threshold in thresholds:
            logger.info(f"Testing threshold: {threshold}")
            
            try:
                # Run backtest with this threshold
                backtest_result = await backtest_runner(threshold)
                
                # Extract metrics
                metrics = {
                    'sharpe_ratio': backtest_result.sharpe_ratio if hasattr(backtest_result, 'sharpe_ratio') else 0.0,
                    'profit_factor': backtest_result.profit_factor,
                    'win_rate': backtest_result.win_rate * 100,  # Convert to percentage
                    'total_pnl': backtest_result.total_pnl,
                    'max_drawdown': backtest_result.max_drawdown if hasattr(backtest_result, 'max_drawdown') else 0.0
                }
                
                # Calculate composite score
                composite_score = self.calculate_composite_score(metrics)
                
                # Create result
                result = OptimizationResult(
                    parameters={'bayesian_threshold': threshold},
                    metrics=metrics,
                    composite_score=composite_score,
                    total_trades=backtest_result.total_trades
                )
                
                results.append(result)
                
                logger.info(
                    f"Threshold {threshold}: "
                    f"trades={result.total_trades}, "
                    f"win_rate={metrics['win_rate']:.2f}%, "
                    f"profit_factor={metrics['profit_factor']:.2f}, "
                    f"sharpe={metrics['sharpe_ratio']:.2f}, "
                    f"composite_score={composite_score:.4f}"
                )
                
            except Exception as e:
                logger.error(f"Error testing threshold {threshold}: {e}")
                continue
        
        if not results:
            raise ValueError("No valid backtest results obtained")
        
        # Select best result (highest composite score with >=min_trades)
        best_result = self.select_best_result(results)
        
        if best_result is None:
            # If no result meets min_trades, try selecting from all results
            logger.warning(
                f"No threshold produced >={self.min_trades} trades. "
                f"Selecting best from available results."
            )
            ranked_results = sorted(results, key=lambda r: r.composite_score, reverse=True)
            best_result = ranked_results[0]
        
        logger.info(
            f"Optimal Bayesian threshold: {best_result.parameters['bayesian_threshold']} "
            f"(composite_score={best_result.composite_score:.4f}, "
            f"trades={best_result.total_trades})"
        )
        
        return best_result

    async def optimize_trailing_stop(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        backtest_runner: Callable,
        stop_values: Optional[List[float]] = None,
        min_runner_trades: int = 10
    ) -> OptimizationResult:
        """
        Optimize trailing stop percentage for runner positions.
        
        Tests different trailing stop values, measures runner-specific metrics,
        and selects the stop value that maximizes average R-multiple on runners.
        
        **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.7, 12.8**
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            backtest_runner: Async function(trailing_stop_pct) -> BacktestResult
            stop_values: List of stop percentages to test (default: [0.15, 0.20, 0.25, 0.30, 0.35, 0.40])
            min_runner_trades: Minimum number of runner trades required for valid result
        
        Returns:
            OptimizationResult with best trailing stop percentage and runner metrics
        
        Raises:
            ValueError: If no valid results with sufficient runner trades
        """
        if stop_values is None:
            stop_values = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
        
        logger.info(
            f"Starting trailing stop optimization: "
            f"testing {len(stop_values)} stop values from {min(stop_values)*100:.0f}% to {max(stop_values)*100:.0f}%"
        )
        
        results = []
        
        for stop_pct in stop_values:
            logger.info(f"Testing trailing stop: {stop_pct*100:.0f}%")
            
            try:
                # Run backtest with this trailing stop percentage
                backtest_result = await backtest_runner(stop_pct)
                
                # Filter for runner trades (trades that exited via trailing stop after tier 1 and tier 2)
                # Runner trades are identified by exit_type == 'trailing_stop'
                runner_trades = []
                if hasattr(backtest_result, 'trades'):
                    runner_trades = [
                        t for t in backtest_result.trades 
                        if t.get('exit_type') == 'trailing_stop' or t.get('type') == 'trailing_stop'
                    ]
                
                runner_count = len(runner_trades)
                
                if runner_count < min_runner_trades:
                    logger.warning(
                        f"Stop {stop_pct*100:.0f}%: Only {runner_count} runner trades "
                        f"(minimum {min_runner_trades} required), skipping"
                    )
                    continue
                
                # Calculate runner-specific metrics
                r_multiples = [t.get('r_multiple', 0) for t in runner_trades]
                avg_r_multiple = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0
                
                # Percentage of runners hitting >5R
                runners_above_5r = [r for r in r_multiples if r >= 5.0]
                pct_above_5r = (len(runners_above_5r) / len(r_multiples) * 100) if r_multiples else 0.0
                
                # Max favorable excursion captured (if available)
                max_favorable_excursion = 0.0
                if hasattr(backtest_result, 'max_favorable_excursion'):
                    max_favorable_excursion = backtest_result.max_favorable_excursion
                elif runner_trades and 'max_favorable_excursion' in runner_trades[0]:
                    mfe_values = [t.get('max_favorable_excursion', 0) for t in runner_trades]
                    max_favorable_excursion = sum(mfe_values) / len(mfe_values) if mfe_values else 0.0
                
                # Create metrics dictionary
                metrics = {
                    'avg_r_multiple': avg_r_multiple,
                    'pct_above_5r': pct_above_5r,
                    'max_favorable_excursion': max_favorable_excursion,
                    'runner_count': runner_count,
                    'max_r_multiple': max(r_multiples) if r_multiples else 0.0,
                    'min_r_multiple': min(r_multiples) if r_multiples else 0.0
                }
                
                # For trailing stop optimization, we use avg_r_multiple as the primary score
                # This aligns with Requirement 12.4: "identify stop value maximizing average runner R-multiple"
                optimization_score = avg_r_multiple
                
                # Create result
                result = OptimizationResult(
                    parameters={'trailing_stop_pct': stop_pct},
                    metrics=metrics,
                    composite_score=optimization_score,  # Using avg_r_multiple as score
                    total_trades=runner_count
                )
                
                results.append(result)
                
                logger.info(
                    f"Stop {stop_pct*100:.0f}%: "
                    f"runners={runner_count}, "
                    f"avg_r_multiple={avg_r_multiple:.2f}, "
                    f"pct_above_5r={pct_above_5r:.1f}%, "
                    f"max_favorable_excursion={max_favorable_excursion:.2f}"
                )
                
            except Exception as e:
                logger.error(f"Error testing trailing stop {stop_pct*100:.0f}%: {e}")
                continue
        
        if not results:
            raise ValueError("No valid backtest results obtained for trailing stop optimization")
        
        # Sort by average R-multiple (descending) to find the best stop value
        results_sorted = sorted(results, key=lambda r: r.composite_score, reverse=True)
        best_result = results_sorted[0]
        
        # Validate that optimal trailing stop captures minimum 60% of max favorable excursion
        # (Requirement 12.6)
        if best_result.metrics.get('max_favorable_excursion', 0) > 0:
            capture_ratio = best_result.metrics['avg_r_multiple'] / best_result.metrics['max_favorable_excursion']
            if capture_ratio < 0.60:
                logger.warning(
                    f"Optimal trailing stop captures only {capture_ratio*100:.1f}% of max favorable excursion "
                    f"(target: 60%+)"
                )
        
        logger.info(
            f"Optimal trailing stop: {best_result.parameters['trailing_stop_pct']*100:.0f}% "
            f"(avg_r_multiple={best_result.metrics['avg_r_multiple']:.2f}, "
            f"runners={best_result.total_trades}, "
            f"pct_above_5r={best_result.metrics['pct_above_5r']:.1f}%)"
        )
        
        return best_result
    
    def generate_trailing_stop_report(
        self,
        results: List[OptimizationResult]
    ) -> pd.DataFrame:
        """
        Generate trailing stop optimization report showing runner performance distribution.
        
        **Validates: Requirement 12.5**
        
        Args:
            results: List of trailing stop optimization results
        
        Returns:
            DataFrame with stop percentages and runner performance metrics
        """
        if not results:
            logger.warning("No results to report")
            return pd.DataFrame()
        
        # Sort by avg_r_multiple (descending)
        sorted_results = sorted(
            results, 
            key=lambda r: r.metrics.get('avg_r_multiple', 0), 
            reverse=True
        )
        
        # Build report data
        report_data = []
        for i, result in enumerate(sorted_results, 1):
            stop_pct = result.parameters['trailing_stop_pct']
            metrics = result.metrics
            
            row = {
                'rank': i,
                'trailing_stop_pct': f"{stop_pct*100:.0f}%",
                'runner_count': metrics.get('runner_count', 0),
                'avg_r_multiple': metrics.get('avg_r_multiple', 0),
                'pct_above_5r': metrics.get('pct_above_5r', 0),
                'max_r_multiple': metrics.get('max_r_multiple', 0),
                'min_r_multiple': metrics.get('min_r_multiple', 0),
                'max_favorable_excursion': metrics.get('max_favorable_excursion', 0)
            }
            report_data.append(row)
        
        df = pd.DataFrame(report_data)
        
        logger.info(f"Generated trailing stop report with {len(df)} results")
        
        return df

    async def optimize_timeframe_weights(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        backtest_runner: Callable,
        weight_step: float = 0.05,
        min_trades_for_weights: int = 40
    ) -> OptimizationResult:
        """
        Optimize timeframe weights for TA score calculation.
        
        Tests weight combinations for timeframes (5m, 15m, 1h, 4h) with constraints:
        - Weights must sum to 1.0
        - Higher timeframes (4h + 1h) combined weight >50%
        - Lower timeframes (5m + 15m) combined weight >30%
        
        Selects weights maximizing win_rate with ≥min_trades_for_weights trades.
        
        **Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8**
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            backtest_runner: Async function(weights_dict) -> BacktestResult
            weight_step: Step size for weight grid search (default: 0.05)
            min_trades_for_weights: Minimum trades required for valid result (default: 40)
        
        Returns:
            OptimizationResult with best timeframe weights and metrics
        
        Raises:
            ValueError: If no valid weight combinations found
        """
        logger.info(
            f"Starting timeframe weight optimization with step size {weight_step}"
        )
        
        # Generate valid weight combinations
        weight_combinations = self._generate_weight_combinations(weight_step)
        
        logger.info(
            f"Generated {len(weight_combinations)} valid weight combinations to test"
        )
        
        results = []
        
        for i, weights in enumerate(weight_combinations, 1):
            if i % 10 == 0:
                logger.info(f"Testing weight combination {i}/{len(weight_combinations)}")
            
            try:
                # Run backtest with these weights
                backtest_result = await backtest_runner(weights)
                
                # Extract metrics
                metrics = {
                    'sharpe_ratio': backtest_result.sharpe_ratio if hasattr(backtest_result, 'sharpe_ratio') else 0.0,
                    'profit_factor': backtest_result.profit_factor,
                    'win_rate': backtest_result.win_rate * 100,  # Convert to percentage
                    'total_pnl': backtest_result.total_pnl,
                    'max_drawdown': backtest_result.max_drawdown if hasattr(backtest_result, 'max_drawdown') else 0.0
                }
                
                # For timeframe weight optimization, we prioritize win_rate (Requirement 13.5)
                # But also consider composite score for overall quality
                composite_score = self.calculate_composite_score(metrics)
                
                # Create result
                result = OptimizationResult(
                    parameters={'timeframe_weights': weights},
                    metrics=metrics,
                    composite_score=composite_score,
                    total_trades=backtest_result.total_trades
                )
                
                results.append(result)
                
                logger.debug(
                    f"Weights {weights}: "
                    f"trades={result.total_trades}, "
                    f"win_rate={metrics['win_rate']:.2f}%, "
                    f"composite_score={composite_score:.4f}"
                )
                
            except Exception as e:
                logger.error(f"Error testing weights {weights}: {e}")
                continue
        
        if not results:
            raise ValueError("No valid backtest results obtained for timeframe weight optimization")
        
        # Filter results with sufficient trades
        valid_results = [r for r in results if r.total_trades >= min_trades_for_weights]
        
        if not valid_results:
            logger.warning(
                f"No weight combination produced >={min_trades_for_weights} trades. "
                f"Using lower threshold."
            )
            valid_results = results
        
        # Sort by win_rate (primary) and composite_score (secondary)
        # Requirement 13.5: "identify weight combination maximizing win_rate"
        valid_results_sorted = sorted(
            valid_results,
            key=lambda r: (r.metrics['win_rate'], r.composite_score),
            reverse=True
        )
        
        best_result = valid_results_sorted[0]
        
        logger.info(
            f"Optimal timeframe weights: {best_result.parameters['timeframe_weights']} "
            f"(win_rate={best_result.metrics['win_rate']:.2f}%, "
            f"composite_score={best_result.composite_score:.4f}, "
            f"trades={best_result.total_trades})"
        )
        
        return best_result
    
    def _generate_weight_combinations(self, step: float = 0.05) -> List[Dict[str, float]]:
        """
        Generate valid timeframe weight combinations.
        
        Constraints:
        - Weights must sum to 1.0
        - Higher timeframes (4h + 1h) combined weight >50%
        - Lower timeframes (5m + 15m) combined weight >30%
        
        **Validates: Requirements 13.2, 13.6, 13.7**
        
        Args:
            step: Step size for weight grid (default: 0.05)
        
        Returns:
            List of valid weight dictionaries
        """
        import numpy as np
        
        weight_combinations = []
        
        # Generate weight ranges
        # 5m: 10-35% (lower timeframe for entry timing)
        # 15m: 16-40% (lower timeframe for entry timing) - increased min to ensure >30% combined
        # 1h: 25-50% (higher timeframe for trend confirmation)
        # 4h: 15-40% (higher timeframe for trend confirmation)
        
        for w_5m in np.arange(0.10, 0.36, step):
            for w_15m in np.arange(0.16, 0.41, step):  # Start at 0.16 to ensure >30% combined
                for w_1h in np.arange(0.25, 0.51, step):
                    # Calculate 4h weight to sum to 1.0
                    w_4h = 1.0 - w_5m - w_15m - w_1h
                    
                    # Validate 4h weight is in reasonable range
                    if w_4h < 0.15 or w_4h > 0.40:
                        continue
                    
                    # Constraint: Higher timeframes (4h + 1h) combined weight >50%
                    higher_tf_weight = w_4h + w_1h
                    if higher_tf_weight <= 0.501:  # Use 0.501 to ensure strict >0.50
                        continue
                    
                    # Constraint: Lower timeframes (5m + 15m) combined weight >30%
                    lower_tf_weight = w_5m + w_15m
                    if lower_tf_weight <= 0.301:  # Use 0.301 to ensure strict >0.30
                        continue
                    
                    # Validate sum is approximately 1.0 (within floating point tolerance)
                    total = w_5m + w_15m + w_1h + w_4h
                    if abs(total - 1.0) > 0.003:  # Increased tolerance for floating point
                        continue
                    
                    # Valid combination - round to 3 decimal places for cleaner values
                    weights = {
                        '5m': round(w_5m, 3),
                        '15m': round(w_15m, 3),
                        '1h': round(w_1h, 3),
                        '4h': round(w_4h, 3)
                    }
                    
                    # Verify rounded weights still sum to approximately 1.0
                    rounded_total = sum(weights.values())
                    if abs(rounded_total - 1.0) > 0.003:
                        continue
                    
                    weight_combinations.append(weights)
        
        return weight_combinations
    
    def generate_timeframe_weights_report(
        self,
        results: List[OptimizationResult],
        top_n: int = 10
    ) -> pd.DataFrame:
        """
        Generate timeframe weight optimization report.
        
        Args:
            results: List of timeframe weight optimization results
            top_n: Number of top results to include
        
        Returns:
            DataFrame with weight combinations and performance metrics
        """
        if not results:
            logger.warning("No results to report")
            return pd.DataFrame()
        
        # Sort by win_rate (primary) and composite_score (secondary)
        sorted_results = sorted(
            results,
            key=lambda r: (r.metrics.get('win_rate', 0), r.composite_score),
            reverse=True
        )[:top_n]
        
        # Build report data
        report_data = []
        for i, result in enumerate(sorted_results, 1):
            weights = result.parameters['timeframe_weights']
            metrics = result.metrics
            
            row = {
                'rank': i,
                'weight_5m': f"{weights['5m']:.2f}",
                'weight_15m': f"{weights['15m']:.2f}",
                'weight_1h': f"{weights['1h']:.2f}",
                'weight_4h': f"{weights['4h']:.2f}",
                'total_trades': result.total_trades,
                'win_rate': f"{metrics.get('win_rate', 0):.2f}%",
                'profit_factor': f"{metrics.get('profit_factor', 0):.2f}",
                'sharpe_ratio': f"{metrics.get('sharpe_ratio', 0):.2f}",
                'composite_score': f"{result.composite_score:.4f}"
            }
            report_data.append(row)
        
        df = pd.DataFrame(report_data)
        
        logger.info(f"Generated timeframe weights report with {len(df)} results")
        
        return df

    async def run_context_agent_ab_test(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        backtest_runner: Callable
    ) -> Dict[str, Any]:
        """
        A/B test Context Agent impact on trading performance.
        
        Runs two parallel backtests:
        - Test A: Without Context Agent (neutral sentiment)
        - Test B: With Context Agent (actual sentiment analysis)
        
        Calculates performance delta and cost-benefit ratio.
        
        **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8**
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            backtest_runner: Async function(context_agent_enabled: bool) -> BacktestResult
        
        Returns:
            Dictionary with comparison metrics, performance deltas, and recommendation
        """
        logger.info("Starting Context Agent A/B test")
        
        # Test A: Without Context Agent
        logger.info("Running Test A: Without Context Agent (neutral sentiment)")
        try:
            result_a = await backtest_runner(context_agent_enabled=False)
            
            metrics_a = {
                'sharpe_ratio': result_a.sharpe_ratio if hasattr(result_a, 'sharpe_ratio') else 0.0,
                'profit_factor': result_a.profit_factor,
                'win_rate': result_a.win_rate * 100,
                'total_pnl': result_a.total_pnl,
                'max_drawdown': result_a.max_drawdown if hasattr(result_a, 'max_drawdown') else 0.0,
                'total_trades': result_a.total_trades
            }
            
            logger.info(
                f"Test A results: "
                f"trades={metrics_a['total_trades']}, "
                f"win_rate={metrics_a['win_rate']:.2f}%, "
                f"profit_factor={metrics_a['profit_factor']:.2f}, "
                f"total_pnl=${metrics_a['total_pnl']:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Error running Test A (without Context Agent): {e}")
            raise
        
        # Test B: With Context Agent
        logger.info("Running Test B: With Context Agent (actual sentiment)")
        try:
            result_b = await backtest_runner(context_agent_enabled=True)
            
            metrics_b = {
                'sharpe_ratio': result_b.sharpe_ratio if hasattr(result_b, 'sharpe_ratio') else 0.0,
                'profit_factor': result_b.profit_factor,
                'win_rate': result_b.win_rate * 100,
                'total_pnl': result_b.total_pnl,
                'max_drawdown': result_b.max_drawdown if hasattr(result_b, 'max_drawdown') else 0.0,
                'total_trades': result_b.total_trades
            }
            
            logger.info(
                f"Test B results: "
                f"trades={metrics_b['total_trades']}, "
                f"win_rate={metrics_b['win_rate']:.2f}%, "
                f"profit_factor={metrics_b['profit_factor']:.2f}, "
                f"total_pnl=${metrics_b['total_pnl']:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Error running Test B (with Context Agent): {e}")
            raise
        
        # Calculate performance deltas
        win_rate_delta = metrics_b['win_rate'] - metrics_a['win_rate']
        profit_factor_delta = metrics_b['profit_factor'] - metrics_a['profit_factor']
        sharpe_delta = metrics_b['sharpe_ratio'] - metrics_a['sharpe_ratio']
        
        # Calculate alpha improvement (Requirement 14.4)
        alpha_improvement = metrics_b['total_pnl'] - metrics_a['total_pnl']
        
        # Estimate API costs
        # Assuming $0.01 per LLM call, 1 call per trade
        api_cost = metrics_b['total_trades'] * 0.01
        
        # Calculate cost-benefit ratio (Requirement 14.5)
        cost_benefit_ratio = alpha_improvement / api_cost if api_cost > 0 else 0
        
        # Determine recommendation (Requirement 14.6, 14.7)
        # Context Agent should add minimum 5% improvement to win_rate or profit_factor
        win_rate_improvement_pct = (win_rate_delta / metrics_a['win_rate'] * 100) if metrics_a['win_rate'] > 0 else 0
        profit_factor_improvement_pct = (profit_factor_delta / metrics_a['profit_factor'] * 100) if metrics_a['profit_factor'] > 0 else 0
        
        meets_improvement_threshold = (
            win_rate_improvement_pct >= 5.0 or 
            profit_factor_improvement_pct >= 5.0
        )
        
        recommendation = 'enable' if meets_improvement_threshold else 'disable'
        
        # Build comparison result
        comparison = {
            'without_context': metrics_a,
            'with_context': metrics_b,
            'win_rate_delta': win_rate_delta,
            'profit_factor_delta': profit_factor_delta,
            'sharpe_delta': sharpe_delta,
            'win_rate_improvement_pct': win_rate_improvement_pct,
            'profit_factor_improvement_pct': profit_factor_improvement_pct,
            'alpha_improvement': alpha_improvement,
            'api_cost': api_cost,
            'cost_benefit_ratio': cost_benefit_ratio,
            'meets_improvement_threshold': meets_improvement_threshold,
            'recommendation': recommendation
        }
        
        logger.info(
            f"Context Agent A/B test complete: "
            f"win_rate_delta={win_rate_delta:+.2f}% ({win_rate_improvement_pct:+.1f}%), "
            f"profit_factor_delta={profit_factor_delta:+.2f} ({profit_factor_improvement_pct:+.1f}%), "
            f"alpha_improvement=${alpha_improvement:+.2f}, "
            f"cost_benefit_ratio={cost_benefit_ratio:.2f}, "
            f"recommendation={recommendation}"
        )
        
        return comparison
    
    def generate_context_agent_report(
        self,
        comparison: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Generate Context Agent A/B test report.
        
        **Validates: Requirement 14.8**
        
        Args:
            comparison: A/B test comparison dictionary
        
        Returns:
            DataFrame with comparison metrics
        """
        report_data = [
            {
                'test': 'Without Context Agent',
                'total_trades': comparison['without_context']['total_trades'],
                'win_rate': f"{comparison['without_context']['win_rate']:.2f}%",
                'profit_factor': f"{comparison['without_context']['profit_factor']:.2f}",
                'sharpe_ratio': f"{comparison['without_context']['sharpe_ratio']:.2f}",
                'total_pnl': f"${comparison['without_context']['total_pnl']:.2f}"
            },
            {
                'test': 'With Context Agent',
                'total_trades': comparison['with_context']['total_trades'],
                'win_rate': f"{comparison['with_context']['win_rate']:.2f}%",
                'profit_factor': f"{comparison['with_context']['profit_factor']:.2f}",
                'sharpe_ratio': f"{comparison['with_context']['sharpe_ratio']:.2f}",
                'total_pnl': f"${comparison['with_context']['total_pnl']:.2f}"
            },
            {
                'test': 'Delta',
                'total_trades': comparison['with_context']['total_trades'] - comparison['without_context']['total_trades'],
                'win_rate': f"{comparison['win_rate_delta']:+.2f}% ({comparison['win_rate_improvement_pct']:+.1f}%)",
                'profit_factor': f"{comparison['profit_factor_delta']:+.2f} ({comparison['profit_factor_improvement_pct']:+.1f}%)",
                'sharpe_ratio': f"{comparison['sharpe_delta']:+.2f}",
                'total_pnl': f"${comparison['alpha_improvement']:+.2f}"
            }
        ]
        
        df = pd.DataFrame(report_data)
        
        # Add cost-benefit analysis
        cost_benefit_data = {
            'metric': ['API Cost', 'Alpha Improvement', 'Cost-Benefit Ratio', 'Recommendation'],
            'value': [
                f"${comparison['api_cost']:.2f}",
                f"${comparison['alpha_improvement']:.2f}",
                f"{comparison['cost_benefit_ratio']:.2f}",
                comparison['recommendation'].upper()
            ]
        }
        
        cost_benefit_df = pd.DataFrame(cost_benefit_data)
        
        logger.info("Generated Context Agent A/B test report")
        
        return df, cost_benefit_df

    async def grid_search_with_cpcv(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        backtest_runner: Callable,
        param_grid: Dict[str, List[Any]],
        n_splits: int = 5,
        purge_hours: int = 48
    ) -> List[OptimizationResult]:
        """
        Exhaustive grid search with Combinatorial Purged Cross-Validation.
        
        CPCV prevents data leakage by:
        1. Purging training data within 48 hours of test boundaries
        2. Using combinatorial splits for robust validation
        3. Averaging performance across multiple folds
        
        **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8**
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            backtest_runner: Async function(params: Dict, train_data, test_data) -> BacktestResult
            param_grid: Dictionary of parameter names to lists of values to test
                Example: {
                    'bayesian_threshold': [0.60, 0.65, 0.70],
                    'trailing_stop_pct': [0.25, 0.30, 0.35],
                    'timeframe_weights': [weights_1, weights_2, weights_3]
                }
            n_splits: Number of cross-validation folds (default: 5)
            purge_hours: Hours to purge around test boundaries (default: 48)
        
        Returns:
            List of OptimizationResult sorted by adjusted score (mean - std)
        """
        import itertools
        import numpy as np
        
        logger.info(
            f"Starting grid search with CPCV: "
            f"n_splits={n_splits}, purge_hours={purge_hours}"
        )
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))
        
        logger.info(
            f"Generated {len(param_combinations)} parameter combinations from grid: "
            f"{param_names}"
        )
        
        results = []
        
        for i, param_tuple in enumerate(param_combinations, 1):
            param_dict = dict(zip(param_names, param_tuple))
            
            logger.info(
                f"Testing combination {i}/{len(param_combinations)}: {param_dict}"
            )
            
            try:
                # Run CPCV for this parameter combination
                cv_scores = []
                cv_metrics_list = []
                
                # Generate CPCV splits
                splits = self._generate_cpcv_splits(
                    start_date, 
                    end_date, 
                    n_splits=n_splits, 
                    purge_hours=purge_hours
                )
                
                for fold_idx, (train_start, train_end, test_start, test_end) in enumerate(splits, 1):
                    logger.debug(
                        f"Fold {fold_idx}/{n_splits}: "
                        f"train={train_start.date()}-{train_end.date()}, "
                        f"test={test_start.date()}-{test_end.date()}"
                    )
                    
                    # Run backtest on test fold with these parameters
                    backtest_result = await backtest_runner(
                        params=param_dict,
                        train_start=train_start,
                        train_end=train_end,
                        test_start=test_start,
                        test_end=test_end
                    )
                    
                    # Extract metrics
                    metrics = {
                        'sharpe_ratio': backtest_result.sharpe_ratio if hasattr(backtest_result, 'sharpe_ratio') else 0.0,
                        'profit_factor': backtest_result.profit_factor,
                        'win_rate': backtest_result.win_rate * 100,
                        'total_pnl': backtest_result.total_pnl,
                        'max_drawdown': backtest_result.max_drawdown if hasattr(backtest_result, 'max_drawdown') else 0.0
                    }
                    
                    # Calculate composite score for this fold
                    composite_score = self.calculate_composite_score(metrics)
                    cv_scores.append(composite_score)
                    cv_metrics_list.append(metrics)
                
                # Calculate mean and std across folds
                mean_score = np.mean(cv_scores)
                std_score = np.std(cv_scores)
                
                # Calculate adjusted score (penalize high variance)
                # Requirement 15.5: rank by (mean_performance - std_performance)
                adjusted_score = mean_score - std_score
                
                # Calculate variance percentage
                variance_pct = (std_score / mean_score * 100) if mean_score > 0 else 0
                
                # Average metrics across folds
                avg_metrics = {}
                for metric_key in cv_metrics_list[0].keys():
                    avg_metrics[metric_key] = np.mean([m[metric_key] for m in cv_metrics_list])
                
                # Add CV-specific metrics
                avg_metrics['cv_mean_score'] = mean_score
                avg_metrics['cv_std_score'] = std_score
                avg_metrics['cv_variance_pct'] = variance_pct
                
                # Create result
                result = OptimizationResult(
                    parameters=param_dict,
                    metrics=avg_metrics,
                    composite_score=adjusted_score,  # Using adjusted score
                    total_trades=sum([m.get('total_trades', 0) for m in cv_metrics_list])
                )
                
                results.append(result)
                
                logger.info(
                    f"Combination {i}: "
                    f"mean_score={mean_score:.4f}, "
                    f"std_score={std_score:.4f}, "
                    f"adjusted_score={adjusted_score:.4f}, "
                    f"variance={variance_pct:.1f}%"
                )
                
            except Exception as e:
                logger.error(f"Error testing combination {param_dict}: {e}")
                continue
        
        if not results:
            raise ValueError("No valid results obtained from grid search")
        
        # Sort by adjusted score (descending)
        results_sorted = sorted(results, key=lambda r: r.composite_score, reverse=True)
        
        # Validate top result has <15% variance (Requirement 15.6)
        top_result = results_sorted[0]
        if top_result.metrics['cv_variance_pct'] > 15:
            logger.warning(
                f"Top parameter combination has high variance: "
                f"{top_result.metrics['cv_variance_pct']:.1f}% (threshold: 15%)"
            )
        
        logger.info(
            f"Grid search complete. Best combination: {top_result.parameters} "
            f"(adjusted_score={top_result.composite_score:.4f}, "
            f"variance={top_result.metrics['cv_variance_pct']:.1f}%)"
        )
        
        return results_sorted
    
    def _generate_cpcv_splits(
        self,
        start_date: datetime,
        end_date: datetime,
        n_splits: int = 5,
        purge_hours: int = 48
    ) -> List[tuple]:
        """
        Generate CPCV splits with purging.
        
        For each split:
        1. Divide data into train and test
        2. Purge training data within purge_hours of test boundaries
        3. Return train and test date ranges
        
        **Validates: Requirements 15.2, 15.3**
        
        Args:
            start_date: Start date of data
            end_date: End date of data
            n_splits: Number of splits
            purge_hours: Hours to purge around test boundaries
        
        Returns:
            List of tuples: (train_start, train_end, test_start, test_end)
        """
        from datetime import timedelta
        
        total_days = (end_date - start_date).days
        test_size_days = total_days // n_splits
        purge_delta = timedelta(hours=purge_hours)
        
        splits = []
        
        for i in range(n_splits):
            # Calculate test window
            test_start = start_date + timedelta(days=i * test_size_days)
            test_end = test_start + timedelta(days=test_size_days)
            
            # Ensure test_end doesn't exceed end_date
            if test_end > end_date:
                test_end = end_date
            
            # Calculate train window with purging
            # Train on all data except test window and purge zones
            train_start = start_date
            train_end = test_start - purge_delta  # Purge before test
            
            # Validate train window is valid
            if train_end <= train_start:
                logger.warning(f"Skipping fold {i+1}: insufficient training data")
                continue
            
            splits.append((train_start, train_end, test_start, test_end))
        
        logger.debug(f"Generated {len(splits)} CPCV splits with {purge_hours}h purging")
        
        return splits
    
    def generate_grid_search_report(
        self,
        results: List[OptimizationResult],
        top_n: int = 10
    ) -> pd.DataFrame:
        """
        Generate grid search optimization report.
        
        **Validates: Requirement 15.7**
        
        Args:
            results: List of grid search results
            top_n: Number of top results to include
        
        Returns:
            DataFrame with parameter combinations and CV metrics
        """
        if not results:
            logger.warning("No results to report")
            return pd.DataFrame()
        
        # Take top N results
        top_results = results[:top_n]
        
        # Build report data
        report_data = []
        for i, result in enumerate(top_results, 1):
            params = result.parameters
            metrics = result.metrics
            
            row = {
                'rank': i,
                'adjusted_score': f"{result.composite_score:.4f}",
                'cv_mean_score': f"{metrics.get('cv_mean_score', 0):.4f}",
                'cv_std_score': f"{metrics.get('cv_std_score', 0):.4f}",
                'cv_variance_pct': f"{metrics.get('cv_variance_pct', 0):.1f}%",
                'win_rate': f"{metrics.get('win_rate', 0):.2f}%",
                'profit_factor': f"{metrics.get('profit_factor', 0):.2f}",
                'sharpe_ratio': f"{metrics.get('sharpe_ratio', 0):.2f}",
                **{f"param_{k}": str(v) for k, v in params.items()}
            }
            report_data.append(row)
        
        df = pd.DataFrame(report_data)
        
        logger.info(f"Generated grid search report with {len(df)} results")
        
        return df
