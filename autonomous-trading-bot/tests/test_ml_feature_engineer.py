"""
Unit tests for ML Feature Engineering Module
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.ml_feature_engineer import MLFeatureEngineer


@pytest.fixture
def sample_trade_history():
    """Create sample trade history for testing."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1h')
    
    return pd.DataFrame({
        'timestamp': dates,
        'symbol': ['BTC/USDT'] * 100,
        'ta_score': np.random.uniform(50, 90, 100),
        'volume_spike': np.random.uniform(0.8, 2.0, 100),
        'sentiment': np.random.choice(['bullish', 'bearish', 'neutral'], 100),
        'volatility_percentile': np.random.uniform(20, 80, 100),
        'trend_strength': np.random.uniform(0.3, 0.9, 100),
        'r_multiple': np.random.uniform(-1, 5, 100)
    })


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    dates = pd.date_range(start='2023-12-01', periods=300, freq='1h')
    
    df = pd.DataFrame({
        'open': np.random.uniform(40000, 45000, 300),
        'high': np.random.uniform(40000, 45000, 300),
        'low': np.random.uniform(40000, 45000, 300),
        'close': np.random.uniform(40000, 45000, 300),
        'volume': np.random.uniform(100, 1000, 300)
    }, index=dates)
    
    # Add ATR
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    
    return {'BTC/USDT': df}


class TestMLFeatureEngineer:
    """Test suite for MLFeatureEngineer class."""
    
    def test_initialization(self, sample_trade_history, sample_market_data):
        """Test feature engineer initialization."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        
        assert engineer is not None
        assert len(engineer.trade_history) == 100
        assert 'BTC/USDT' in engineer.market_data
    
    def test_create_base_features(self, sample_trade_history, sample_market_data):
        """Test base feature creation."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        features = engineer.create_base_features()
        
        # Check all base features exist
        assert 'ta_score' in features.columns
        assert 'volume_spike' in features.columns
        assert 'sentiment_score' in features.columns
        assert 'volatility_percentile' in features.columns
        assert 'trend_strength' in features.columns
        
        # Check feature count
        assert len(features) == 100
    
    def test_create_derived_features(self, sample_trade_history, sample_market_data):
        """Test derived feature creation."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        features = engineer.create_derived_features()
        
        # Check derived features exist
        assert 'score_momentum' in features.columns
        assert 'volume_acceleration' in features.columns
        assert 'sentiment_shift' in features.columns
        
        # Check feature count
        assert len(features) == 100
    
    def test_create_market_regime_features(self, sample_trade_history, sample_market_data):
        """Test market regime feature creation."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        features = engineer.create_market_regime_features()
        
        # Check regime features exist
        assert 'bull_market' in features.columns
        assert 'bear_market' in features.columns
        assert 'high_volatility' in features.columns
        assert 'low_volatility' in features.columns
        
        # Check binary values
        assert features['bull_market'].isin([0, 1]).all()
        assert features['bear_market'].isin([0, 1]).all()
    
    def test_create_temporal_features(self, sample_trade_history, sample_market_data):
        """Test temporal feature creation."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        features = engineer.create_temporal_features()
        
        # Check temporal features exist
        assert 'hour_of_day' in features.columns
        assert 'day_of_week' in features.columns
        assert 'days_since_last_trade' in features.columns
        
        # Check value ranges
        assert features['hour_of_day'].between(0, 23).all()
        assert features['day_of_week'].between(0, 6).all()
        assert (features['days_since_last_trade'] >= 0).all()
    
    def test_normalize_features(self, sample_trade_history, sample_market_data):
        """Test feature normalization."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        
        # Create features with known range
        features = pd.DataFrame({
            'feature1': [0, 50, 100],
            'feature2': [10, 20, 30]
        })
        
        normalized = engineer.normalize_features(features)
        
        # Check normalization to 0-1 range
        assert normalized['feature1'].min() == 0.0
        assert normalized['feature1'].max() == 1.0
        assert normalized['feature2'].min() == 0.0
        assert normalized['feature2'].max() == 1.0
    
    def test_create_target_variable(self, sample_trade_history, sample_market_data):
        """Test target variable creation."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        target = engineer.create_target_variable()
        
        # Check binary values
        assert target.isin([0, 1]).all()
        
        # Check target logic (R-multiple > 1.5)
        for idx, r_mult in enumerate(sample_trade_history['r_multiple']):
            expected = 1 if r_mult > 1.5 else 0
            assert target.iloc[idx] == expected
    
    def test_extract_features_complete_pipeline(self, sample_trade_history, sample_market_data):
        """Test complete feature extraction pipeline."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        features = engineer.extract_features()
        
        # Check target variable exists
        assert 'target' in features.columns
        
        # Check no missing values
        assert not features.isna().any().any()
        
        # Check feature count
        assert len(features) == 100
        
        # Check normalized range (excluding target)
        numeric_cols = features.select_dtypes(include=[np.number]).columns
        numeric_cols = numeric_cols.drop('target')
        
        for col in numeric_cols:
            assert features[col].min() >= 0.0
            assert features[col].max() <= 1.0
    
    def test_sentiment_to_score(self, sample_trade_history, sample_market_data):
        """Test sentiment conversion to numeric score."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        
        assert engineer._sentiment_to_score('bullish') == 1.0
        assert engineer._sentiment_to_score('bearish') == -1.0
        assert engineer._sentiment_to_score('neutral') == 0.0
        assert engineer._sentiment_to_score('unknown') == 0.0
    
    def test_handle_missing_values(self, sample_trade_history, sample_market_data):
        """Test missing value handling."""
        # Create data with missing values
        trade_history = sample_trade_history.copy()
        trade_history.loc[10:20, 'ta_score'] = np.nan
        trade_history.loc[30:35, 'volume_spike'] = np.nan
        
        engineer = MLFeatureEngineer(trade_history, sample_market_data)
        features = engineer.extract_features()
        
        # Check no missing values remain
        assert not features.isna().any().any()
    
    def test_transform_new_data(self, sample_trade_history, sample_market_data):
        """Test transformation of new data using stored parameters."""
        engineer = MLFeatureEngineer(sample_trade_history, sample_market_data)
        
        # Extract features to store normalization parameters
        _ = engineer.extract_features()
        
        # Create new data
        new_data = pd.DataFrame({
            'ta_score': [75.0],
            'volume_spike': [1.5]
        })
        
        # Transform new data
        transformed = engineer.transform_new_data(new_data)
        
        # Check normalization applied
        assert 'ta_score' in transformed.columns
        assert 'volume_spike' in transformed.columns
        assert transformed['ta_score'].iloc[0] >= 0.0
        assert transformed['ta_score'].iloc[0] <= 1.0
    
    def test_empty_trade_history(self, sample_market_data):
        """Test handling of empty trade history."""
        empty_history = pd.DataFrame()
        engineer = MLFeatureEngineer(empty_history, sample_market_data)
        
        # Should not raise error
        features = engineer.create_base_features()
        assert len(features) == 0
    
    def test_missing_market_data(self, sample_trade_history):
        """Test handling of missing market data."""
        empty_market_data = {}
        engineer = MLFeatureEngineer(sample_trade_history, empty_market_data)
        
        # Should not raise error, use defaults
        features = engineer.create_market_regime_features()
        assert len(features) == 100
        
        # All regime features should be 0 (default)
        assert (features['bull_market'] == 0).all()
        assert (features['bear_market'] == 0).all()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
