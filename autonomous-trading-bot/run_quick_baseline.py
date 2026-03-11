"""
Quick Baseline Backtest for Task 3.14 - Demo Version

Uses 3 months of recent data to demonstrate baseline backtest functionality.
For production, use run_baseline_backtest.py with full 2021-2024 data.

**Validates: Requirements 6.1, 6.2, 7.1, 7.2, 7.7**
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import json

from loguru import logger
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.historical_data_collector import HistoricalDataCollector
from src.cycle_replay_engine import CycleReplayEngine, BacktestConfig, Position
from src.performance_metrics_calculator import PerformanceMetricsCalculator
from src.exchange_ccxt import ExchangeConnector


class SimpleSignalGenerator:
    """Simple signal generator for baseline backtest."""
    
    def __init__(self, bayesian_threshold: float = 0.65):
        self.bayesian_threshold = bayesian_threshold
        self.signal_count = 0
        self.last_signal_time = {}
        self.min_signal_interval = timedelta(hours=4)  # Minimum 4 hours between signals per symbol
    
    def generate_signals(
        self,
        timestamp: datetime,
        market_data: Dict[str, Dict]
    ) -> List[Dict]:
        """Generate trading signals based on simple TA criteria."""
        signals = []
        
        for symbol, timeframe_data in market_data.items():
            # Check minimum interval
            if symbol in self.last_signal_time:
                if timestamp - self.last_signal_time[symbol] < self.min_signal_interval:
                    continue
            
            candle_5m = timeframe_data.get('5m')
            candle_1h = timeframe_data.get('1h')
            
            if not candle_5m or not candle_1h:
                continue
            
            # Simple momentum: 5m close > 1h close (uptrend)
            if candle_5m['close'] <= candle_1h['close']:
                continue
            
            # Volume spike check
            if 'volume_ma' in candle_5m and candle_5m['volume_ma'] > 0:
                volume_spike = candle_5m['volume'] / candle_5m['volume_ma']
                if volume_spike < 1.3:  # Lowered threshold for more signals
                    continue
            
            # Price momentum (5m close > 5m open)
            if candle_5m['close'] <= candle_5m['open']:
                continue
            
            # Calculate TA score
            if 'high_20' in candle_5m and 'low_20' in candle_5m:
                price_range = candle_5m['high_20'] - candle_5m['low_20']
                if price_range > 0:
                    price_position = (candle_5m['close'] - candle_5m['low_20']) / price_range
                    ta_score = price_position * 100
                else:
                    ta_score = 50
            else:
                ta_score = 70
            
            if ta_score < 60:  # Lowered threshold
                continue
            
            # Entry and stop
            entry_price = candle_5m['close']
            atr = candle_5m.get('atr', entry_price * 0.02)
            stop_loss = entry_price - (2 * atr)
            take_profit = entry_price + (5 * atr)
            
            # Simplified posterior calculation
            posterior = 0.70  # Fixed for baseline
            
            if posterior < self.bayesian_threshold:
                continue
            
            signal = {
                'symbol': symbol,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'posterior': posterior,
                'setup_type': 'momentum',
                'atr_pct': (atr / entry_price) * 100,
                'ta_score': ta_score
            }
            
            signals.append(signal)
            self.signal_count += 1
            self.last_signal_time[symbol] = timestamp
        
        return signals


async def collect_quick_data():
    """Collect 3 months of data for quick baseline."""
    logger.info("Collecting 3 months of data for quick baseline...")
    
    symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
    timeframes = ["5m", "1h"]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    exchange = ExchangeConnector(name="binance", sandbox=False)
    await exchange.initialize()
    
    collector = HistoricalDataCollector(
        exchange=exchange,
        storage_path="./data/quick_baseline"
    )
    
    results = await collector.collect_bulk_and_save(
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        max_concurrent=3,
        validate=False  # Skip validation for speed
    )
    
    await exchange.close()
    
    # Check success
    success_count = sum(
        1 for symbol_results in results.values()
        for path, _ in symbol_results.values()
        if path is not None
    )
    
    logger.info(f"Collected {success_count}/{len(symbols)*len(timeframes)} datasets")
    return success_count >= len(symbols) * len(timeframes) * 0.8


async def run_quick_baseline():
    """Run quick baseline backtest on 3 months of data."""
    logger.info("=" * 80)
    logger.info("QUICK BASELINE BACKTEST - Task 3.14 Demo")
    logger.info("=" * 80)
    logger.info("NOTE: This is a 3-month demo. For full baseline, use run_baseline_backtest.py")
    logger.info("=" * 80)
    
    # Check if data exists, collect if not
    data_path = Path("./data/quick_baseline")
    if not data_path.exists() or not list(data_path.glob("*/5m/data.parquet")):
        logger.info("Data not found. Collecting...")
        success = await collect_quick_data()
        if not success:
            logger.error("Data collection failed!")
            return None
    
    # Configuration
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
    timeframes = ["5m", "1h"]
    
    logger.info(f"Period: {start_date.date()} to {end_date.date()}")
    logger.info(f"Symbols: {symbols}")
    
    # Initialize
    exchange = ExchangeConnector(name="binance", sandbox=False)
    data_collector = HistoricalDataCollector(
        exchange=exchange,
        storage_path="./data/quick_baseline"
    )
    
    config = BacktestConfig(
        initial_capital=100000.0,
        position_size_pct=0.02,
        bayesian_threshold=0.65,
        runner_trailing_stop_pct=0.25,
        max_positions=3  # Reduced for quick test
    )
    
    engine = CycleReplayEngine(data_loader=data_collector, config=config)
    signal_generator = SimpleSignalGenerator(bayesian_threshold=config.bayesian_threshold)
    
    # Load data
    logger.info("Loading historical data...")
    all_data = {}
    for symbol in symbols:
        all_data[symbol] = {}
        for tf in timeframes:
            df = data_collector.load_from_parquet(symbol, tf)
            if df is not None and not df.empty:
                df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
                all_data[symbol][tf] = df
                logger.info(f"Loaded {symbol} {tf}: {len(df)} candles")
    
    if not all_data:
        logger.error("No data loaded!")
        return None
    
    # Run backtest
    logger.info("Running backtest simulation...")
    current_time = start_date
    cycle_interval = timedelta(minutes=5)
    cycle_count = 0
    
    while current_time <= end_date:
        # Prepare market data
        market_data = {}
        for symbol, tf_data in all_data.items():
            market_data[symbol] = {}
            for tf, df in tf_data.items():
                candles = df[df['timestamp'] <= current_time]
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
                    candle_dict['atr'] = high_low.tail(14).mean()
                
                market_data[symbol][tf] = candle_dict
        
        if not market_data:
            current_time += cycle_interval
            continue
        
        # Generate signals
        signals = signal_generator.generate_signals(current_time, market_data)
        
        # Simulate cycle
        await engine.simulate_cycle(current_time, market_data, signals)
        
        cycle_count += 1
        if cycle_count % 500 == 0:
            logger.info(
                f"Progress: {cycle_count} cycles, equity: ${engine.equity:,.2f}, "
                f"positions: {len(engine.positions)}, trades: {len(engine.closed_trades)}"
            )
        
        current_time += cycle_interval
    
    logger.info(f"Simulation complete: {cycle_count} cycles, {len(engine.closed_trades)} trades")
    
    if len(engine.closed_trades) == 0:
        logger.error("No trades executed!")
        return None
    
    # Calculate metrics
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
    logger.info("QUICK BASELINE RESULTS")
    logger.info("=" * 80)
    logger.info(f"Period: {start_date.date()} to {end_date.date()} (3 months)")
    logger.info(f"Initial Capital: ${config.initial_capital:,.2f}")
    logger.info(f"Final Equity: ${engine.equity:,.2f}")
    logger.info(f"Total PnL: ${engine.equity - config.initial_capital:,.2f}")
    logger.info(f"Return: {((engine.equity / config.initial_capital) - 1) * 100:.2f}%")
    logger.info("-" * 80)
    logger.info(f"Total Trades: {metrics.total_trades}")
    logger.info(f"Win Rate: {metrics.win_rate:.2f}%")
    logger.info(f"Profit Factor: {metrics.profit_factor:.2f}")
    logger.info(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    logger.info(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
    logger.info(f"Avg R-Multiple: {metrics.avg_r_multiple:.2f}R")
    logger.info("=" * 80)
    
    # Save results
    results_dir = Path("./backtest_results")
    results_dir.mkdir(exist_ok=True)
    
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"quick_baseline_{timestamp_str}.json"
    
    results_data = {
        "run_info": {
            "run_id": f"quick_baseline_{timestamp_str}",
            "run_type": "quick_baseline_demo",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": symbols,
            "note": "3-month demo backtest"
        },
        "config": {
            "initial_capital": config.initial_capital,
            "bayesian_threshold": config.bayesian_threshold,
            "runner_trailing_stop_pct": config.runner_trailing_stop_pct
        },
        "metrics": metrics.to_dict(),
        "final_equity": engine.equity,
        "total_pnl": engine.equity - config.initial_capital
    }
    
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2, default=str)
    
    logger.info(f"Results saved to: {results_file}")
    logger.info("=" * 80)
    
    return results_data


if __name__ == "__main__":
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    try:
        results = asyncio.run(run_quick_baseline())
        if results:
            logger.info("✓ Quick baseline backtest completed!")
            logger.info("For full baseline (2021-2024), run: python run_baseline_backtest.py")
            sys.exit(0)
        else:
            logger.error("✗ Quick baseline failed!")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)
