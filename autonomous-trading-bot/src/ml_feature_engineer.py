"""
ML Feature Engineering Module

Extracts and transforms features from historical trade data for ML model training.
Implements comprehensive feature engineering including base features, derived features,
market regime indicators, and temporal features.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MLFeatureEngineer:
    """
    Feature engineering module for ML training pipeline.
    
    Extracts features from trade history and market data, creates derived features,
    adds market regime indicators, normalizes features, and creates target variable.
    """
    
    def __init__(self, trade_history: pd.DataFrame, market_data: Dict[str, pd.DataFrame]):
        """
        Initialize feature engineer.
        
        Args:
            trade_history: DataFrame with historical trades and setup data
            market_data: Dict mapping symbols to OHLCV DataFrames
        """
        self.trade_history = trade_history.copy()
        self.market_data = market_data
        self.feature_mins = {}
        self.feature_maxs = {}
        
    def extract_features(self) -> pd.DataFrame:
        """
        Extract all features for ML training.
        
        Complete pipeline:
        1. Create base features from trade setups
        2. Create derived features (momentum, acceleration)
        3. Create market regime features
        4. Create temporal features
        5. Normalize to 0-1 range
        6. Handle missing values
        7. Create target variable
        
        Returns:
            DataFrame with all features and target variable
        """
        logger.info("Starting feature extraction pipeline")
        
        # Create base features
        features = self.create_base_features()
        logger.info(f"Created {len(features.columns)} base features")
        
        # Add derived features
        derived = self.create_derived_features()
        features = pd.concat([features, derived], axis=1)
        logger.info(f"Added {len(derived.columns)} derived features")
        
        # Add market regime features
        regime = self.create_market_regime_features()
        features = pd.concat([features, regime], axis=1)
        logger.info(f"Added {len(regime.columns)} market regime features")
        
        # Add temporal features
        temporal = self.create_temporal_features()
        features = pd.concat([features, temporal], axis=1)
        logger.info(f"Added {len(temporal.columns)} temporal features")
        
        # Normalize features
        features = self.normalize_features(features)
        logger.info("Normalized features to 0-1 range")
        
        # Handle missing values
        features = self._handle_missing_values(features)
        logger.info("Handled missing values")
        
        # Create target variable
        features['target'] = self.create_target_variable()
        logger.info("Created target variable")
        
        logger.info(f"Feature extraction complete: {len(features)} samples, {len(features.columns)} features")
        return features
    
    def create_base_features(self) -> pd.DataFrame:
        """
        Create base features from trade setups.
        
        Base features include:
        - ta_score: Technical analysis score (0-100)
        - volume_spike: Volume spike ratio
        - sentiment_score: LLM sentiment (-1 to 1)
        - volatility_percentile: ATR percentile (0-100)
        - trend_strength: EMA alignment score
        
        Returns:
            DataFrame with base features
        """
        features = pd.DataFrame(index=self.trade_history.index)
        
        # TA score
        features['ta_score'] = self.trade_history.get('ta_score', 50.0)
        
        # Volume spike
        features['volume_spike'] = self.trade_history.get('volume_spike', 1.0)
        
        # Sentiment score
        if 'sentiment' in self.trade_history.columns:
            features['sentiment_score'] = self.trade_history['sentiment'].apply(self._sentiment_to_score)
        else:
            features['sentiment_score'] = 0.0
        
        # Volatility percentile
        features['volatility_percentile'] = self.trade_history.get('volatility_percentile', 50.0)
        
        # Trend strength
        features['trend_strength'] = self.trade_history.get('trend_strength', 0.5)
        
        return features
    
    def create_derived_features(self) -> pd.DataFrame:
        """
        Create derived features from base features.
        
        Derived features include:
        - score_momentum: TA score change rate
        - volume_acceleration: Volume change rate
        - sentiment_shift: Sentiment change from previous
        
        Returns:
            DataFrame with derived features
        """
        features = pd.DataFrame(index=self.trade_history.index)
        
        # Score momentum (change in TA score)
        if 'ta_score' in self.trade_history.columns:
            features['score_momentum'] = self.trade_history['ta_score'].diff().fillna(0)
        else:
            features['score_momentum'] = 0.0
        
        # Volume acceleration (change in volume spike)
        if 'volume_spike' in self.trade_history.columns:
            features['volume_acceleration'] = self.trade_history['volume_spike'].diff().fillna(0)
        else:
            features['volume_acceleration'] = 0.0
        
        # Sentiment shift
        if 'sentiment' in self.trade_history.columns:
            sentiment_scores = self.trade_history['sentiment'].apply(self._sentiment_to_score)
            features['sentiment_shift'] = sentiment_scores.diff().fillna(0)
        else:
            features['sentiment_shift'] = 0.0
        
        return features
    
    def create_market_regime_features(self) -> pd.DataFrame:
        """
        Create market regime indicators.
        
        Market regime features include:
        - bull_market: 50-day EMA > 200-day EMA
        - bear_market: 50-day EMA < 200-day EMA
        - high_volatility: ATR > 80th percentile
        - low_volatility: ATR < 20th percentile
        
        Returns:
            DataFrame with market regime features
        """
        features = pd.DataFrame(index=self.trade_history.index)
        
        # Initialize with defaults
        features['bull_market'] = 0
        features['bear_market'] = 0
        features['high_volatility'] = 0
        features['low_volatility'] = 0
        
        # Calculate regime for each symbol
        if 'symbol' in self.trade_history.columns and 'timestamp' in self.trade_history.columns:
            for idx, row in self.trade_history.iterrows():
                symbol = row['symbol']
                timestamp = row['timestamp']
                
                if symbol in self.market_data:
                    regime = self._calculate_market_regime(symbol, timestamp)
                    features.loc[idx, 'bull_market'] = regime['bull_market']
                    features.loc[idx, 'bear_market'] = regime['bear_market']
                    features.loc[idx, 'high_volatility'] = regime['high_volatility']
                    features.loc[idx, 'low_volatility'] = regime['low_volatility']
        
        return features
    
    def create_temporal_features(self) -> pd.DataFrame:
        """
        Create time-based features.
        
        Temporal features include:
        - hour_of_day: 0-23
        - day_of_week: 0-6 (Monday=0)
        - days_since_last_trade: Days since last trade
        
        Returns:
            DataFrame with temporal features
        """
        features = pd.DataFrame(index=self.trade_history.index)
        
        if 'timestamp' in self.trade_history.columns:
            timestamps = pd.to_datetime(self.trade_history['timestamp'])
            
            # Hour of day
            features['hour_of_day'] = timestamps.dt.hour
            
            # Day of week
            features['day_of_week'] = timestamps.dt.dayofweek
            
            # Days since last trade
            features['days_since_last_trade'] = timestamps.diff().dt.total_seconds() / 86400
            features['days_since_last_trade'] = features['days_since_last_trade'].fillna(0)
        else:
            features['hour_of_day'] = 12
            features['day_of_week'] = 0
            features['days_since_last_trade'] = 0
        
        return features
    
    def normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize features to 0-1 range using min-max scaling.
        
        Args:
            df: DataFrame with features to normalize
            
        Returns:
            DataFrame with normalized features
        """
        normalized = df.copy()
        
        # Select numeric columns (exclude target if present)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if 'target' in numeric_cols:
            numeric_cols = numeric_cols.drop('target')
        
        # Min-max normalization
        for col in numeric_cols:
            col_min = df[col].min()
            col_max = df[col].max()
            
            # Store for later use (e.g., transforming new data)
            self.feature_mins[col] = col_min
            self.feature_maxs[col] = col_max
            
            # Normalize
            if col_max > col_min:
                normalized[col] = (df[col] - col_min) / (col_max - col_min)
            else:
                normalized[col] = 0.5  # Default to middle if no variance
        
        return normalized
    
    def create_target_variable(self) -> pd.Series:
        """
        Create binary target variable.
        
        Target = 1 if R-multiple > 1.5, else 0
        
        Returns:
            Series with binary target values
        """
        if 'r_multiple' in self.trade_history.columns:
            target = (self.trade_history['r_multiple'] > 1.5).astype(int)
        else:
            # Default to 0 if r_multiple not available
            target = pd.Series(0, index=self.trade_history.index)
        
        return target
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values in features.
        
        Strategy:
        - Forward-fill for time-series features
        - Median-fill for cross-sectional features
        
        Args:
            df: DataFrame with potential missing values
            
        Returns:
            DataFrame with missing values handled
        """
        filled = df.copy()
        
        # Forward fill time-series features
        time_series_features = ['score_momentum', 'volume_acceleration', 'sentiment_shift', 'days_since_last_trade']
        for col in time_series_features:
            if col in filled.columns:
                filled[col] = filled[col].ffill()
        
        # Median fill remaining
        numeric_cols = filled.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if filled[col].isna().any():
                filled[col] = filled[col].fillna(filled[col].median())
        
        # Fill any remaining NaN with 0
        filled.fillna(0, inplace=True)
        
        return filled
    
    def _sentiment_to_score(self, sentiment: str) -> float:
        """
        Convert sentiment string to numeric score.
        
        Args:
            sentiment: Sentiment string (bullish/bearish/neutral)
            
        Returns:
            Numeric score: 1.0 for bullish, -1.0 for bearish, 0.0 for neutral
        """
        if isinstance(sentiment, str):
            sentiment_lower = sentiment.lower()
            if 'bullish' in sentiment_lower:
                return 1.0
            elif 'bearish' in sentiment_lower:
                return -1.0
        return 0.0
    
    def _calculate_market_regime(self, symbol: str, timestamp: datetime) -> Dict:
        """
        Calculate market regime indicators for a symbol at a timestamp.
        
        Args:
            symbol: Trading symbol
            timestamp: Timestamp for regime calculation
            
        Returns:
            Dict with regime indicators
        """
        regime = {
            'bull_market': 0,
            'bear_market': 0,
            'high_volatility': 0,
            'low_volatility': 0
        }
        
        try:
            df = self.market_data[symbol]
            
            # Filter data up to timestamp
            df_filtered = df[df.index <= timestamp].tail(200)
            
            if len(df_filtered) < 50:
                return regime
            
            # Calculate EMAs
            ema_50 = df_filtered['close'].ewm(span=50, adjust=False).mean().iloc[-1]
            ema_200 = df_filtered['close'].ewm(span=200, adjust=False).mean().iloc[-1] if len(df_filtered) >= 200 else ema_50
            
            # Bull/bear market
            if ema_50 > ema_200:
                regime['bull_market'] = 1
            else:
                regime['bear_market'] = 1
            
            # Volatility regime
            if 'atr' in df_filtered.columns or 'high' in df_filtered.columns:
                if 'atr' in df_filtered.columns:
                    atr = df_filtered['atr'].iloc[-1]
                    atr_percentile = (df_filtered['atr'] <= atr).sum() / len(df_filtered) * 100
                else:
                    # Calculate simple ATR if not available
                    high_low = df_filtered['high'] - df_filtered['low']
                    atr = high_low.rolling(14).mean().iloc[-1]
                    atr_percentile = (high_low.rolling(14).mean() <= atr).sum() / len(df_filtered) * 100
                
                if atr_percentile > 80:
                    regime['high_volatility'] = 1
                elif atr_percentile < 20:
                    regime['low_volatility'] = 1
        
        except Exception as e:
            logger.warning(f"Error calculating market regime for {symbol}: {e}")
        
        return regime
    
    def transform_new_data(self, new_data: pd.DataFrame) -> pd.DataFrame:
        """
        Transform new data using stored normalization parameters.
        
        Args:
            new_data: DataFrame with new features to transform
            
        Returns:
            Normalized DataFrame
        """
        transformed = new_data.copy()
        
        for col in self.feature_mins.keys():
            if col in transformed.columns:
                col_min = self.feature_mins[col]
                col_max = self.feature_maxs[col]
                
                if col_max > col_min:
                    transformed[col] = (transformed[col] - col_min) / (col_max - col_min)
                    # Clip to 0-1 range
                    transformed[col] = transformed[col].clip(0, 1)
                else:
                    transformed[col] = 0.5
        
        return transformed
