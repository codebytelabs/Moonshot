"""
Extract ML features from backtest data.

This script loads historical backtest trades, extracts features using MLFeatureEngineer,
validates completeness, and saves the feature matrix for ML model training.

**Validates: Requirements 16.1, 16.2, 16.3, 16.4**
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd
import numpy as np
from loguru import logger

from src.ml_feature_engineer import MLFeatureEngineer
from src.cycle_replay_engine import CycleReplayEngine, BacktestConfig
from src.historical_data_collector import HistoricalDataCollector


async def load_backtest_trades(backtest_results_dir: str = "backtest_results") -> pd.DataFrame:
    """
    Load historical trades from backtest results.
    
    Args:
        backtest_results_dir: Directory containing backtest result files
        
    Returns:
        DataFrame with trade history
    """
    logger.info(f"Loading backtest trades from {backtest_results_dir}")
    
    results_path = Path(backtest_results_dir)
    if not results_path.exists():
        logger.warning(f"Backtest results directory not found: {backtest_results_dir}")
        return pd.DataFrame()
    
    # First, try to load from CSV files (preferred - contains individual trades)
    csv_files = list(results_path.glob("*trades*.csv"))
    if csv_files:
        logger.info(f"Found {len(csv_files)} trade CSV files")
        all_trades = []
        
        for csv_file in csv_files:
            try:
                trades_df = pd.read_csv(csv_file)
                logger.info(f"Loaded {len(trades_df)} trades from {csv_file.name}")
                all_trades.append(trades_df)
            except Exception as e:
                logger.error(f"Error loading {csv_file.name}: {e}")
                continue
        
        if all_trades:
            combined_df = pd.concat(all_trades, ignore_index=True)
            logger.info(f"Total trades loaded from CSV: {len(combined_df)}")
            return combined_df
    
    # Fallback: Try to load from JSON files (may not have individual trades)
    result_files = list(results_path.glob("*.json"))
    if not result_files:
        logger.warning(f"No backtest result files found in {backtest_results_dir}")
        return pd.DataFrame()
    
    logger.info(f"Found {len(result_files)} backtest result JSON files")
    
    # Load trades from all result files
    all_trades = []
    for result_file in result_files:
        try:
            with open(result_file, 'r') as f:
                result_data = json.load(f)
            
            # Check if trades are included in the result
            if 'trades' in result_data:
                trades = result_data['trades']
                logger.info(f"Loaded {len(trades)} trades from {result_file.name}")
                all_trades.extend(trades)
            else:
                logger.warning(f"No trades found in {result_file.name}")
        
        except Exception as e:
            logger.error(f"Error loading {result_file.name}: {e}")
            continue
    
    if not all_trades:
        logger.warning("No trades found in any backtest results")
        return pd.DataFrame()
    
    # Convert to DataFrame
    trades_df = pd.DataFrame(all_trades)
    logger.info(f"Total trades loaded: {len(trades_df)}")
    
    return trades_df


async def enrich_trades_with_features(
    trades_df: pd.DataFrame,
    data_dir: str = "data/quick_baseline"
) -> pd.DataFrame:
    """
    Enrich trade data with features needed for ML.
    
    Since backtest trades may not have all features, we'll add synthetic/default
    features based on available data.
    
    Args:
        trades_df: DataFrame with basic trade data
        data_dir: Directory with historical market data
        
    Returns:
        DataFrame with enriched features
    """
    logger.info("Enriching trades with ML features")
    
    enriched = trades_df.copy()
    
    # Add timestamp if not present
    if 'timestamp' not in enriched.columns:
        if 'entry_timestamp' in enriched.columns:
            enriched['timestamp'] = enriched['entry_timestamp']
        else:
            enriched['timestamp'] = datetime.now()
    
    # Convert timestamp to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(enriched['timestamp']):
        enriched['timestamp'] = pd.to_datetime(enriched['timestamp'])
    
    # Add ta_score (synthetic based on r_multiple if not present)
    if 'ta_score' not in enriched.columns:
        if 'r_multiple' in enriched.columns:
            # Higher R-multiple suggests better TA score
            enriched['ta_score'] = enriched['r_multiple'].apply(
                lambda r: min(100, max(0, 50 + r * 10))
            )
        else:
            enriched['ta_score'] = 50.0
    
    # Add volume_spike (default if not present)
    if 'volume_spike' not in enriched.columns:
        enriched['volume_spike'] = 1.5  # Default moderate spike
    
    # Add sentiment (default neutral if not present)
    if 'sentiment' not in enriched.columns:
        enriched['sentiment'] = 'neutral'
    
    # Add volatility_percentile (default if not present)
    if 'volatility_percentile' not in enriched.columns:
        enriched['volatility_percentile'] = 50.0
    
    # Add trend_strength (default if not present)
    if 'trend_strength' not in enriched.columns:
        enriched['trend_strength'] = 0.5
    
    # Add posterior if not present
    if 'posterior' not in enriched.columns:
        enriched['posterior'] = 0.65  # Default threshold
    
    logger.info(f"Enriched {len(enriched)} trades with features")
    return enriched


async def load_market_data(
    symbols: List[str],
    data_dir: str = "data/quick_baseline"
) -> Dict[str, pd.DataFrame]:
    """
    Load historical market data for feature engineering.
    
    Args:
        symbols: List of trading symbols
        data_dir: Directory with historical data
        
    Returns:
        Dict mapping symbols to OHLCV DataFrames
    """
    logger.info(f"Loading market data for {len(symbols)} symbols from {data_dir}")
    
    market_data = {}
    data_path = Path(data_dir)
    
    for symbol in symbols:
        # Normalize symbol format (BTC/USDT -> BTC_USDT)
        symbol_normalized = symbol.replace('/', '_')
        
        # Try to load 1h data (most useful for regime features)
        symbol_dir = data_path / symbol_normalized / "1h"
        parquet_file = symbol_dir / "data.parquet"
        
        if parquet_file.exists():
            try:
                df = pd.read_parquet(parquet_file)
                df.index = pd.to_datetime(df.index)
                market_data[symbol] = df
                logger.info(f"Loaded {len(df)} candles for {symbol}")
            except Exception as e:
                logger.error(f"Error loading data for {symbol}: {e}")
        else:
            logger.warning(f"No data found for {symbol} at {parquet_file}")
    
    logger.info(f"Loaded market data for {len(market_data)} symbols")
    return market_data


async def extract_and_save_features(
    backtest_results_dir: str = "autonomous-trading-bot/backtest_results",
    data_dir: str = "autonomous-trading-bot/data/quick_baseline",
    output_dir: str = "autonomous-trading-bot/ml_data",
    output_format: str = "parquet"
):
    """
    Main function to extract features from backtest data and save to disk.
    
    Args:
        backtest_results_dir: Directory with backtest results
        data_dir: Directory with historical market data
        output_dir: Directory to save feature matrix
        output_format: Format to save (parquet, csv, or both)
    """
    logger.info("=" * 80)
    logger.info("ML Feature Extraction Pipeline")
    logger.info("=" * 80)
    
    # Step 1: Load backtest trades
    logger.info("\n[Step 1/5] Loading backtest trades...")
    trades_df = await load_backtest_trades(backtest_results_dir)
    
    if trades_df.empty:
        logger.error("No trades found in backtest results. Cannot extract features.")
        logger.info("\nTo generate backtest data with trades, run:")
        logger.info("  python autonomous-trading-bot/run_baseline_backtest.py")
        return
    
    logger.info(f"✓ Loaded {len(trades_df)} trades")
    
    # Step 2: Enrich trades with features
    logger.info("\n[Step 2/5] Enriching trades with ML features...")
    enriched_trades = await enrich_trades_with_features(trades_df, data_dir)
    logger.info(f"✓ Enriched trades with {len(enriched_trades.columns)} columns")
    
    # Step 3: Load market data
    logger.info("\n[Step 3/5] Loading market data...")
    symbols = enriched_trades['symbol'].unique().tolist() if 'symbol' in enriched_trades.columns else []
    market_data = await load_market_data(symbols, data_dir)
    logger.info(f"✓ Loaded market data for {len(market_data)} symbols")
    
    # Step 4: Extract features using MLFeatureEngineer
    logger.info("\n[Step 4/5] Extracting ML features...")
    feature_engineer = MLFeatureEngineer(enriched_trades, market_data)
    features_df = feature_engineer.extract_features()
    
    # Validate no missing features
    missing_count = features_df.isnull().sum().sum()
    if missing_count > 0:
        logger.warning(f"Found {missing_count} missing values in features")
        logger.info("Missing values by column:")
        for col in features_df.columns:
            null_count = features_df[col].isnull().sum()
            if null_count > 0:
                logger.info(f"  {col}: {null_count} missing")
    else:
        logger.info("✓ No missing features detected")
    
    logger.info(f"✓ Extracted {len(features_df)} samples with {len(features_df.columns)} features")
    logger.info(f"  Feature columns: {list(features_df.columns)}")
    
    # Step 5: Save feature matrix to disk
    logger.info("\n[Step 5/5] Saving feature matrix...")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output_format in ["parquet", "both"]:
        parquet_file = output_path / f"ml_features_{timestamp}.parquet"
        features_df.to_parquet(parquet_file, index=False)
        logger.info(f"✓ Saved Parquet: {parquet_file}")
    
    if output_format in ["csv", "both"]:
        csv_file = output_path / f"ml_features_{timestamp}.csv"
        features_df.to_csv(csv_file, index=False)
        logger.info(f"✓ Saved CSV: {csv_file}")
    
    # Save metadata
    metadata = {
        'extraction_timestamp': timestamp,
        'num_samples': len(features_df),
        'num_features': len(features_df.columns) - 1,  # Exclude target
        'feature_columns': list(features_df.columns),
        'source_trades': len(trades_df),
        'symbols': symbols,
        'target_distribution': {
            'positive': int((features_df['target'] == 1).sum()),
            'negative': int((features_df['target'] == 0).sum())
        }
    }
    
    metadata_file = output_path / f"ml_features_{timestamp}_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, indent=2, fp=f)
    logger.info(f"✓ Saved metadata: {metadata_file}")
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("Feature Extraction Summary")
    logger.info("=" * 80)
    logger.info(f"Total samples: {len(features_df)}")
    logger.info(f"Total features: {len(features_df.columns) - 1}")
    logger.info(f"Target distribution:")
    logger.info(f"  Positive (R>1.5): {metadata['target_distribution']['positive']}")
    logger.info(f"  Negative (R≤1.5): {metadata['target_distribution']['negative']}")
    logger.info(f"Output directory: {output_path.absolute()}")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(extract_and_save_features(output_format="both"))
