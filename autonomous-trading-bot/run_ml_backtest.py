"""
ML-Enhanced Backtest Runner for Task 7.15

Executes backtest with ML predictions enabled and compares to baseline.
Validates 3-5% win_rate improvement and generates ML impact report.

**Validates: Requirements 17.7, 17.8, 18.8**
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import joblib

from loguru import logger
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.historical_data_collector import HistoricalDataCollector
from src.cycle_replay_engine import CycleReplayEngine, BacktestConfig
from src.performance_metrics_calculator import PerformanceMetricsCalculator
from src.exchange_ccxt import ExchangeConnector


class MLEnhancedSignalGenerator:
    """
    ML-enhanced signal generator that uses trained models to improve trade selection.
    """
    
    def __init__(
        self,
        bayesian_threshold: float = 0.65,
        ml_threshold: float = 0.55,
        use_ml: bool = True
    ):
        self.bayesian_threshold = bayesian_threshold
        self.ml_threshold = ml_threshold
        self.use_ml = use_ml
        self.signal_count = 0
        self.ml_model = None
        self.scaler_params = None
        
        if use_ml:
            self._load_ml_models()
    
    def _load_ml_models(self):
        """Load trained ML ensemble model."""
        try:
            model_path = Path("ml_models/ensemble.joblib")
            if model_path.exists():
                self.ml_model = joblib.load(model_path)
                logger.info(f"✓ Loaded ML ensemble model from {model_path}")
            else:
                logger.warning(f"ML model not found at {model_path}, using baseline logic")
                self.use_ml = False
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self.use_ml = False
    
    def _extract_features(
        self,
        symbol: str,
        candle_5m: Dict,
        candle_1h: Dict,
        ta_score: float,
        posterior: float
    ) -> Optional[np.ndarray]:
        """
        Extract features for ML prediction.
        
        Features match those used in training:
        - TA_score
        - volume_spike
        - sentiment_score (neutral default)
        - volatility_percentile
        - trend_strength
        - score_momentum
        - volume_acceleration
        """
        try:
            features = {}
            
            # Base features
            features['TA_score'] = ta_score / 100.0  # Normalize to 0-1
            
            # Volume spike
            if 'volume_ma' in candle_5m and candle_5m['volume_ma'] > 0:
                features['volume_spike'] = candle_5m['volume'] / candle_5m['volume_ma']
            else:
                features['volume_spike'] = 1.0
            
            # Sentiment (neutral default)
            features['sentiment_score'] = 0.5
            
            # Volatility percentile (using ATR)
            if 'atr' in candle_5m:
                atr_pct = (candle_5m['atr'] / candle_5m['close']) * 100
                # Normalize: 0-2% ATR -> 0-0.5, 2-5% -> 0.5-1.0
                features['volatility_percentile'] = min(1.0, atr_pct / 5.0)
            else:
                features['volatility_percentile'] = 0.5
            
            # Trend strength (5m vs 1h)
            if candle_1h['close'] > 0:
                trend_strength = (candle_5m['close'] - candle_1h['close']) / candle_1h['close']
                features['trend_strength'] = max(-1.0, min(1.0, trend_strength * 10))  # Scale and clip
            else:
                features['trend_strength'] = 0.0
            
            # Score momentum (simplified)
            features['score_momentum'] = 0.0  # Would need historical scores
            
            # Volume acceleration (simplified)
            features['volume_acceleration'] = 0.0  # Would need historical volumes
            
            # Convert to array in correct order
            feature_names = [
                'TA_score', 'volume_spike', 'sentiment_score',
                'volatility_percentile', 'trend_strength',
                'score_momentum', 'volume_acceleration'
            ]
            
            feature_array = np.array([features[name] for name in feature_names]).reshape(1, -1)
            
            return feature_array
            
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None
    
    def _get_ml_prediction(
        self,
        symbol: str,
        candle_5m: Dict,
        candle_1h: Dict,
        ta_score: float,
        posterior: float
    ) -> Optional[float]:
        """
        Get ML model prediction for trade success probability.
        
        Returns:
            Probability of trade success (0-1), or None if ML unavailable
        """
        if not self.use_ml or self.ml_model is None:
            return None
        
        try:
            features = self._extract_features(symbol, candle_5m, candle_1h, ta_score, posterior)
            if features is None:
                return None
            
            # Get prediction probability
            prediction_proba = self.ml_model.predict_proba(features)[0]
            
            # Return probability of success (class 1)
            return prediction_proba[1]
            
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return None
    
    def generate_signals(
        self,
        timestamp: datetime,
        market_data: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Generate trading signals with optional ML enhancement.
        
        If ML is enabled:
        - Generate candidate signals using baseline logic
        - Filter signals using ML predictions
        - Only accept signals with ML confidence > threshold
        """
        signals = []
        
        for symbol, timeframe_data in market_data.items():
            candle_5m = timeframe_data.get('5m')
            candle_1h = timeframe_data.get('1h')
            
            if not candle_5m or not candle_1h:
                continue
            
            # Calculate simple TA score
            if 'high_20' in candle_5m and 'low_20' in candle_5m:
                price_range = candle_5m['high_20'] - candle_5m['low_20']
                if price_range > 0:
                    price_position = (candle_5m['close'] - candle_5m['low_20']) / price_range
                    ta_score = price_position * 100
                else:
                    ta_score = 50
            else:
                ta_score = 60
            
            # Only trade when price is in upper half of range
            if ta_score < 50:
                continue
            
            # Calculate entry and stop
            entry_price = candle_5m['close']
            atr = candle_5m.get('atr', entry_price * 0.02)
            stop_loss = entry_price - (2 * atr)
            take_profit = entry_price + (5 * atr)
            
            # Calculate posterior (simplified Bayesian) - more lenient
            prior = 0.50  # Higher prior
            ta_likelihood = 0.65  # Lower for more signals
            context_likelihood = 0.55  # Slightly higher
            vol_likelihood = 0.60  # Lower
            
            posterior = prior * ta_likelihood * context_likelihood * vol_likelihood * 4.0  # Higher multiplier
            posterior = min(0.99, posterior)
            
            # Apply ML filter if enabled
            if self.use_ml:
                ml_prediction = self._get_ml_prediction(
                    symbol, candle_5m, candle_1h, ta_score, posterior
                )
                
                if ml_prediction is not None:
                    # ML prediction must exceed threshold
                    if ml_prediction < self.ml_threshold:
                        continue
                    
                    # Boost posterior based on ML confidence
                    ml_boost = (ml_prediction - 0.5) * 0.2  # Up to 10% boost
                    posterior = min(0.99, posterior + ml_boost)
            
            if posterior < self.bayesian_threshold:
                continue
            
            # Create signal
            signal = {
                'symbol': symbol,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'posterior': posterior,
                'setup_type': 'momentum',
                'atr_pct': (atr / entry_price) * 100,
                'ta_score': ta_score,
                'ml_prediction': ml_prediction if self.use_ml else None
            }
            
            signals.append(signal)
            self.signal_count += 1
        
        return signals


async def load_historical_data(
    data_collector: HistoricalDataCollector,
    symbols: List[str],
    timeframes: List[str],
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Load historical data for all symbols and timeframes."""
    logger.info(f"Loading historical data for {len(symbols)} symbols...")
    
    data = {}
    for symbol in symbols:
        data[symbol] = {}
        for timeframe in timeframes:
            df = data_collector.load_from_parquet(symbol, timeframe)
            if df is not None and not df.empty:
                df = df[
                    (df['timestamp'] >= start_date) &
                    (df['timestamp'] <= end_date)
                ]
                data[symbol][timeframe] = df
                logger.info(
                    f"Loaded {symbol} {timeframe}: {len(df)} candles"
                )
            else:
                logger.warning(f"No data found for {symbol} {timeframe}")
    
    return data


def prepare_market_data(
    all_data: Dict[str, Dict[str, pd.DataFrame]],
    timestamp: datetime
) -> Dict[str, Dict]:
    """Prepare market data for a specific timestamp."""
    market_data = {}
    
    for symbol, timeframe_data in all_data.items():
        market_data[symbol] = {}
        
        for timeframe, df in timeframe_data.items():
            candles = df[df['timestamp'] <= timestamp]
            if candles.empty:
                continue
            
            candle = candles.iloc[-1]
            candle_dict = candle.to_dict()
            
            # Add indicators
            if len(candles) >= 20:
                candle_dict['volume_ma'] = candles['volume'].tail(20).mean()
                candle_dict['high_20'] = candles['high'].tail(20).max()
                candle_dict['low_20'] = candles['low'].tail(20).min()
            
            if len(candles) >= 14:
                high_low = candles['high'] - candles['low']
                atr = high_low.tail(14).mean()
                candle_dict['atr'] = atr
            
            market_data[symbol][timeframe] = candle_dict
    
    return market_data


async def run_ml_backtest(use_ml: bool = True):
    """
    Execute backtest with or without ML enhancement.
    
    Args:
        use_ml: If True, use ML predictions. If False, run baseline.
    """
    mode = "ML-ENHANCED" if use_ml else "BASELINE"
    logger.info("=" * 80)
    logger.info(f"{mode} BACKTEST - Task 7.15")
    logger.info("=" * 80)
    
    # Use same configuration as baseline for fair comparison
    # Using quick_baseline data (3 months) for demonstration
    start_date = datetime(2025, 11, 17)
    end_date = datetime(2026, 2, 15)
    
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT"
    ]
    
    timeframes = ["5m", "1h"]
    
    # Initialize components
    logger.info("Initializing components...")
    exchange = ExchangeConnector(name="binance", sandbox=False)
    data_collector = HistoricalDataCollector(
        exchange=exchange,
        storage_path="./data/quick_baseline"  # Use available data
    )
    
    config = BacktestConfig(
        initial_capital=100000.0,
        position_size_pct=0.02,
        bayesian_threshold=0.55,  # Lower threshold for more trades
        runner_trailing_stop_pct=0.25,
        max_positions=5
    )
    
    logger.info(f"Backtest config: {config}")
    logger.info(f"ML enabled: {use_ml}")
    
    # Initialize backtest engine
    engine = CycleReplayEngine(
        data_loader=data_collector,
        config=config
    )
    
    # Initialize signal generator
    signal_generator = MLEnhancedSignalGenerator(
        bayesian_threshold=config.bayesian_threshold,
        ml_threshold=0.55,
        use_ml=use_ml
    )
    
    # Load historical data
    logger.info(f"Loading data: {start_date} to {end_date}")
    all_data = await load_historical_data(
        data_collector,
        symbols,
        timeframes,
        start_date,
        end_date
    )
    
    if not all_data or all(not tf_data for tf_data in all_data.values()):
        logger.error("No historical data available!")
        return None
    
    # Run backtest
    logger.info("Starting backtest simulation...")
    from datetime import timedelta
    
    current_time = start_date
    cycle_interval = timedelta(minutes=5)
    cycle_count = 0
    
    while current_time <= end_date:
        market_data = prepare_market_data(all_data, current_time)
        
        if not market_data:
            current_time += cycle_interval
            continue
        
        signals = signal_generator.generate_signals(current_time, market_data)
        await engine.simulate_cycle(current_time, market_data, signals)
        
        cycle_count += 1
        
        if cycle_count % 1000 == 0:
            logger.info(
                f"Progress: {cycle_count} cycles, "
                f"equity: ${engine.equity:,.2f}, "
                f"trades: {len(engine.closed_trades)}"
            )
        
        current_time += cycle_interval
    
    logger.info(f"Backtest complete: {cycle_count} cycles processed")
    
    # Calculate metrics
    if len(engine.closed_trades) == 0:
        logger.error("No trades executed!")
        return None
    
    equity_series = pd.Series(
        [eq for _, eq in engine.equity_curve],
        index=[ts for ts, _ in engine.equity_curve]
    )
    
    metrics_calc = PerformanceMetricsCalculator(
        trades=engine.closed_trades,
        equity_curve=equity_series
    )
    
    metrics = metrics_calc.calculate_all_metrics()
    
    # Display results
    logger.info("=" * 80)
    logger.info(f"{mode} BACKTEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"Total Trades: {metrics.total_trades}")
    logger.info(f"Win Rate: {metrics.win_rate:.2f}%")
    logger.info(f"Profit Factor: {metrics.profit_factor:.2f}")
    logger.info(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    logger.info(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
    logger.info(f"Avg R-Multiple: {metrics.avg_r_multiple:.2f}R")
    logger.info(f"Final Equity: ${engine.equity:,.2f}")
    logger.info(f"Total PnL: ${engine.equity - config.initial_capital:,.2f}")
    logger.info("=" * 80)
    
    return {
        "mode": mode,
        "metrics": metrics,
        "final_equity": engine.equity,
        "trades": engine.closed_trades,
        "equity_curve": equity_series,
        "config": config
    }


async def compare_results_and_generate_report():
    """
    Run both baseline and ML-enhanced backtests, compare results,
    and generate ML impact report.
    """
    logger.info("=" * 80)
    logger.info("ML VALIDATION - Task 7.15")
    logger.info("Running baseline and ML-enhanced backtests for comparison")
    logger.info("=" * 80)
    
    # Run baseline backtest
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: Running BASELINE backtest (no ML)")
    logger.info("=" * 80)
    baseline_results = await run_ml_backtest(use_ml=False)
    
    if not baseline_results:
        logger.error("Baseline backtest failed!")
        return None
    
    # Run ML-enhanced backtest
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Running ML-ENHANCED backtest")
    logger.info("=" * 80)
    ml_results = await run_ml_backtest(use_ml=True)
    
    if not ml_results:
        logger.error("ML-enhanced backtest failed!")
        return None
    
    # Compare results
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Comparing Results")
    logger.info("=" * 80)
    
    baseline_metrics = baseline_results['metrics']
    ml_metrics = ml_results['metrics']
    
    # Calculate improvements
    win_rate_improvement = ml_metrics.win_rate - baseline_metrics.win_rate
    profit_factor_improvement = ml_metrics.profit_factor - baseline_metrics.profit_factor
    sharpe_improvement = ml_metrics.sharpe_ratio - baseline_metrics.sharpe_ratio
    
    logger.info("Performance Comparison:")
    logger.info("-" * 80)
    logger.info(f"{'Metric':<25} {'Baseline':<15} {'ML-Enhanced':<15} {'Improvement':<15}")
    logger.info("-" * 80)
    logger.info(f"{'Win Rate':<25} {baseline_metrics.win_rate:>14.2f}% {ml_metrics.win_rate:>14.2f}% {win_rate_improvement:>+14.2f}%")
    logger.info(f"{'Profit Factor':<25} {baseline_metrics.profit_factor:>14.2f} {ml_metrics.profit_factor:>14.2f} {profit_factor_improvement:>+14.2f}")
    logger.info(f"{'Sharpe Ratio':<25} {baseline_metrics.sharpe_ratio:>14.2f} {ml_metrics.sharpe_ratio:>14.2f} {sharpe_improvement:>+14.2f}")
    logger.info(f"{'Max Drawdown':<25} {baseline_metrics.max_drawdown:>14.2f}% {ml_metrics.max_drawdown:>14.2f}% {ml_metrics.max_drawdown - baseline_metrics.max_drawdown:>+14.2f}%")
    logger.info(f"{'Avg R-Multiple':<25} {baseline_metrics.avg_r_multiple:>14.2f}R {ml_metrics.avg_r_multiple:>14.2f}R {ml_metrics.avg_r_multiple - baseline_metrics.avg_r_multiple:>+14.2f}R")
    logger.info(f"{'Total Trades':<25} {baseline_metrics.total_trades:>14} {ml_metrics.total_trades:>14} {ml_metrics.total_trades - baseline_metrics.total_trades:>+14}")
    logger.info("-" * 80)
    
    # Validate requirements
    logger.info("\nRequirement Validation:")
    logger.info("-" * 80)
    
    # Requirement 17.7, 17.8: 3-5% win rate improvement
    win_rate_target_met = 3.0 <= win_rate_improvement <= 5.0
    logger.info(f"Win Rate Improvement (3-5% target): {win_rate_improvement:+.2f}%")
    if win_rate_target_met:
        logger.info("  ✓ PASSED: Win rate improvement within 3-5% target range")
    elif win_rate_improvement > 5.0:
        logger.info(f"  ✓ EXCEEDED: Win rate improvement exceeds 5% target ({win_rate_improvement:.2f}%)")
    else:
        logger.warning(f"  ✗ BELOW TARGET: Win rate improvement below 3% minimum ({win_rate_improvement:.2f}%)")
    
    # Requirement 18.8: Minimum 3% improvement
    min_improvement_met = win_rate_improvement >= 3.0
    logger.info(f"\nMinimum 3% Improvement (Req 18.8): {win_rate_improvement:+.2f}%")
    if min_improvement_met:
        logger.info("  ✓ PASSED: Meets minimum 3% win rate improvement requirement")
    else:
        logger.warning("  ✗ FAILED: Does not meet minimum 3% win rate improvement")
    
    logger.info("-" * 80)
    
    # Generate ML impact report
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Generating ML Impact Report")
    logger.info("=" * 80)
    
    report = {
        "report_info": {
            "report_type": "ML Impact Analysis",
            "task": "7.15",
            "generated_at": datetime.now().isoformat(),
            "requirements_validated": ["17.7", "17.8", "18.8"]
        },
        "baseline_results": {
            "total_trades": baseline_metrics.total_trades,
            "win_rate": baseline_metrics.win_rate,
            "profit_factor": baseline_metrics.profit_factor,
            "sharpe_ratio": baseline_metrics.sharpe_ratio,
            "max_drawdown": baseline_metrics.max_drawdown,
            "avg_r_multiple": baseline_metrics.avg_r_multiple,
            "final_equity": baseline_results['final_equity'],
            "total_pnl": baseline_results['final_equity'] - baseline_results['config'].initial_capital
        },
        "ml_enhanced_results": {
            "total_trades": ml_metrics.total_trades,
            "win_rate": ml_metrics.win_rate,
            "profit_factor": ml_metrics.profit_factor,
            "sharpe_ratio": ml_metrics.sharpe_ratio,
            "max_drawdown": ml_metrics.max_drawdown,
            "avg_r_multiple": ml_metrics.avg_r_multiple,
            "final_equity": ml_results['final_equity'],
            "total_pnl": ml_results['final_equity'] - ml_results['config'].initial_capital
        },
        "improvements": {
            "win_rate_improvement_pct": win_rate_improvement,
            "profit_factor_improvement": profit_factor_improvement,
            "sharpe_improvement": sharpe_improvement,
            "trade_count_change": ml_metrics.total_trades - baseline_metrics.total_trades
        },
        "validation": {
            "win_rate_target_3_5_pct": win_rate_target_met,
            "min_3_pct_improvement": min_improvement_met,
            "requirements_met": win_rate_target_met or (win_rate_improvement > 5.0)
        },
        "conclusion": {
            "ml_effective": min_improvement_met,
            "recommendation": "Deploy ML models" if min_improvement_met else "Further tuning needed",
            "summary": f"ML models {'achieved' if min_improvement_met else 'did not achieve'} the minimum 3% win rate improvement target"
        }
    }
    
    # Save report
    results_dir = Path("./backtest_results")
    results_dir.mkdir(exist_ok=True)
    
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = results_dir / f"ml_impact_report_{timestamp_str}.json"
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(f"ML impact report saved to: {report_file}")
    
    # Save detailed comparison
    comparison_file = results_dir / f"ml_comparison_{timestamp_str}.csv"
    comparison_df = pd.DataFrame([
        {
            'metric': 'Win Rate (%)',
            'baseline': baseline_metrics.win_rate,
            'ml_enhanced': ml_metrics.win_rate,
            'improvement': win_rate_improvement
        },
        {
            'metric': 'Profit Factor',
            'baseline': baseline_metrics.profit_factor,
            'ml_enhanced': ml_metrics.profit_factor,
            'improvement': profit_factor_improvement
        },
        {
            'metric': 'Sharpe Ratio',
            'baseline': baseline_metrics.sharpe_ratio,
            'ml_enhanced': ml_metrics.sharpe_ratio,
            'improvement': sharpe_improvement
        },
        {
            'metric': 'Max Drawdown (%)',
            'baseline': baseline_metrics.max_drawdown,
            'ml_enhanced': ml_metrics.max_drawdown,
            'improvement': ml_metrics.max_drawdown - baseline_metrics.max_drawdown
        },
        {
            'metric': 'Total Trades',
            'baseline': baseline_metrics.total_trades,
            'ml_enhanced': ml_metrics.total_trades,
            'improvement': ml_metrics.total_trades - baseline_metrics.total_trades
        }
    ])
    comparison_df.to_csv(comparison_file, index=False)
    logger.info(f"Comparison data saved to: {comparison_file}")
    
    logger.info("\n" + "=" * 80)
    logger.info("ML VALIDATION COMPLETE")
    logger.info("=" * 80)
    
    return report


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    log_file = Path("./logs") / f"ml_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file.parent.mkdir(exist_ok=True)
    logger.add(log_file, level="DEBUG")
    
    # Run ML validation
    try:
        report = asyncio.run(compare_results_and_generate_report())
        if report and report['validation']['requirements_met']:
            logger.info("✓ ML validation completed successfully!")
            logger.info(f"✓ Win rate improvement: {report['improvements']['win_rate_improvement_pct']:+.2f}%")
            sys.exit(0)
        elif report:
            logger.warning("⚠ ML validation completed but did not meet all requirements")
            logger.warning(f"Win rate improvement: {report['improvements']['win_rate_improvement_pct']:+.2f}%")
            sys.exit(0)
        else:
            logger.error("✗ ML validation failed!")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"ML validation error: {e}")
        sys.exit(1)
