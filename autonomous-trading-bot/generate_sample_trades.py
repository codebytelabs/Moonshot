"""
Generate sample trade data for ML feature extraction demonstration.

This creates synthetic but realistic trade data for testing the ML feature
extraction pipeline when actual backtest data is not available.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json

from loguru import logger


def generate_sample_trades(num_trades: int = 100) -> pd.DataFrame:
    """
    Generate synthetic trade data with realistic distributions.
    
    Args:
        num_trades: Number of trades to generate
        
    Returns:
        DataFrame with synthetic trade data
    """
    logger.info(f"Generating {num_trades} sample trades...")
    
    np.random.seed(42)  # For reproducibility
    
    trades = []
    start_date = datetime(2024, 1, 1)
    
    symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
    setup_types = ["momentum", "breakout", "pullback", "mean_reversion"]
    sentiments = ["bullish", "bearish", "neutral"]
    
    for i in range(num_trades):
        # Random timestamp
        days_offset = np.random.randint(0, 365)
        hours_offset = np.random.randint(0, 24)
        timestamp = start_date + timedelta(days=days_offset, hours=hours_offset)
        
        # Random symbol
        symbol = np.random.choice(symbols)
        
        # Random setup type
        setup_type = np.random.choice(setup_types)
        
        # Generate R-multiple with realistic distribution
        # 50% win rate, winners average 2.5R, losers average -1R
        if np.random.random() < 0.50:
            # Winner
            r_multiple = np.random.exponential(1.5) + 0.5  # Avg ~2R
        else:
            # Loser
            r_multiple = -np.random.exponential(0.7) - 0.3  # Avg ~-1R
        
        # Entry and exit prices
        entry_price = np.random.uniform(100, 50000)
        risk = entry_price * 0.02  # 2% risk
        exit_price = entry_price + (r_multiple * risk)
        
        # Quantity
        quantity = np.random.uniform(0.01, 1.0)
        
        # PnL
        pnl = (exit_price - entry_price) * quantity
        
        # TA score (correlated with R-multiple)
        ta_score = min(100, max(0, 60 + r_multiple * 10 + np.random.normal(0, 10)))
        
        # Volume spike
        volume_spike = np.random.lognormal(0.5, 0.5)  # Avg ~1.6x
        
        # Sentiment (correlated with outcome)
        if r_multiple > 0:
            sentiment = np.random.choice(["bullish", "neutral"], p=[0.7, 0.3])
        else:
            sentiment = np.random.choice(["bearish", "neutral"], p=[0.6, 0.4])
        
        # Volatility percentile
        volatility_percentile = np.random.uniform(20, 80)
        
        # Trend strength
        trend_strength = np.random.beta(2, 2)  # Bell curve around 0.5
        
        # Posterior
        posterior = min(0.99, max(0.50, 0.65 + np.random.normal(0, 0.10)))
        
        trade = {
            'position_id': f'pos_{i:04d}',
            'symbol': symbol,
            'side': 'long',
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'entry_timestamp': timestamp.isoformat(),
            'exit_timestamp': (timestamp + timedelta(hours=np.random.randint(1, 48))).isoformat(),
            'pnl': pnl,
            'r_multiple': r_multiple,
            'setup_type': setup_type,
            'exit_reason': 'take_profit' if r_multiple > 0 else 'stop_loss',
            'fees': abs(pnl) * 0.002,  # 0.2% fees
            'slippage': entry_price * 0.001,  # 0.1% slippage
            'ta_score': ta_score,
            'volume_spike': volume_spike,
            'sentiment': sentiment,
            'volatility_percentile': volatility_percentile,
            'trend_strength': trend_strength,
            'posterior': posterior
        }
        
        trades.append(trade)
    
    trades_df = pd.DataFrame(trades)
    
    # Calculate summary stats
    win_rate = (trades_df['r_multiple'] > 0).mean() * 100
    avg_r = trades_df['r_multiple'].mean()
    
    logger.info(f"Generated {len(trades_df)} trades:")
    logger.info(f"  Win rate: {win_rate:.1f}%")
    logger.info(f"  Avg R-multiple: {avg_r:.2f}R")
    logger.info(f"  Symbols: {trades_df['symbol'].unique().tolist()}")
    logger.info(f"  Setup types: {trades_df['setup_type'].unique().tolist()}")
    
    return trades_df


def save_sample_trades(trades_df: pd.DataFrame, output_dir: str = "backtest_results"):
    """
    Save sample trades to CSV and JSON formats.
    
    Args:
        trades_df: DataFrame with trade data
        output_dir: Directory to save files
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save as CSV
    csv_file = output_path / f"sample_trades_{timestamp}.csv"
    trades_df.to_csv(csv_file, index=False)
    logger.info(f"Saved trades CSV: {csv_file}")
    
    # Save as JSON (for compatibility)
    json_file = output_path / f"sample_backtest_{timestamp}.json"
    
    # Calculate metrics
    winning_trades = (trades_df['r_multiple'] > 0).sum()
    losing_trades = (trades_df['r_multiple'] <= 0).sum()
    win_rate = (winning_trades / len(trades_df)) * 100
    
    result_data = {
        "run_info": {
            "run_id": f"sample_{timestamp}",
            "run_type": "sample_data",
            "start_date": trades_df['entry_timestamp'].min(),
            "end_date": trades_df['entry_timestamp'].max(),
            "symbols": trades_df['symbol'].unique().tolist(),
            "note": "Synthetic sample data for ML feature extraction demo"
        },
        "config": {
            "initial_capital": 100000.0,
            "bayesian_threshold": 0.65,
            "runner_trailing_stop_pct": 0.25
        },
        "metrics": {
            "total_trades": len(trades_df),
            "winning_trades": int(winning_trades),
            "losing_trades": int(losing_trades),
            "win_rate": win_rate,
            "avg_r_multiple": float(trades_df['r_multiple'].mean()),
            "total_pnl": float(trades_df['pnl'].sum())
        },
        "trades": trades_df.to_dict('records')
    }
    
    with open(json_file, 'w') as f:
        json.dump(result_data, f, indent=2)
    
    logger.info(f"Saved backtest JSON: {json_file}")
    
    return csv_file, json_file


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Sample Trade Data Generator")
    logger.info("=" * 80)
    
    # Generate sample trades
    trades_df = generate_sample_trades(num_trades=100)
    
    # Save to files
    csv_file, json_file = save_sample_trades(
        trades_df,
        output_dir="autonomous-trading-bot/backtest_results"
    )
    
    logger.info("=" * 80)
    logger.info("Sample data generation complete!")
    logger.info(f"CSV file: {csv_file}")
    logger.info(f"JSON file: {json_file}")
    logger.info("=" * 80)
    logger.info("\nYou can now run feature extraction:")
    logger.info("  python autonomous-trading-bot/extract_ml_features.py")
