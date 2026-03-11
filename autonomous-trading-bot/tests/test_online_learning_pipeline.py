"""
Unit tests for OnlineLearningPipeline
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from xgboost import XGBClassifier
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from online_learning_pipeline import OnlineLearningPipeline


@pytest.fixture
def sample_features():
    """Generate sample feature data"""
    np.random.seed(42)
    return pd.DataFrame({
        'ta_score': np.random.uniform(50, 90, 100),
        'volume_spike': np.random.uniform(0, 1, 100),
        'sentiment_score': np.random.uniform(0, 1, 100),
        'volatility_percentile': np.random.uniform(0, 1, 100),
        'trend_strength': np.random.uniform(0, 1, 100)
    })


@pytest.fixture
def sample_target():
    """Generate sample target data"""
    np.random.seed(42)
    return pd.Series(np.random.choice([0, 1], size=100, p=[0.4, 0.6]))


@pytest.fixture
def trained_models(sample_features, sample_target):
    """Create trained models for testing"""
    # Train simple models
    rf_model = RandomForestClassifier(n_estimators=10, max_depth=5, random_state=42)
    rf_model.fit(sample_features, sample_target)
    
    gb_model = GradientBoostingClassifier(n_estimators=10, max_depth=5, random_state=42)
    gb_model.fit(sample_features, sample_target)
    
    xgb_model = XGBClassifier(n_estimators=10, max_depth=5, random_state=42, eval_metric='logloss')
    xgb_model.fit(sample_features, sample_target)
    
    ensemble = VotingClassifier(
        estimators=[('rf', rf_model), ('gb', gb_model), ('xgb', xgb_model)],
        voting='soft',
        weights=[0.3, 0.3, 0.4]
    )
    ensemble.fit(sample_features, sample_target)
    
    return {
        'random_forest': rf_model,
        'gradient_boosting': gb_model,
        'xgboost': xgb_model,
        'ensemble': ensemble
    }


@pytest.fixture
def pipeline(trained_models):
    """Create OnlineLearningPipeline instance"""
    return OnlineLearningPipeline(
        base_models=trained_models,
        update_threshold=50,
        rolling_window=1000,
        validation_window=100,
        degradation_threshold=0.10,
        retrain_interval_days=90
    )


class TestOnlineLearningPipelineInitialization:
    """Test pipeline initialization"""
    
    def test_initialization_with_defaults(self, trained_models):
        """Test pipeline initializes with default parameters"""
        pipeline = OnlineLearningPipeline(base_models=trained_models)
        
        assert pipeline.update_threshold == 50
        assert pipeline.rolling_window == 1000
        assert pipeline.validation_window == 100
        assert pipeline.degradation_threshold == 0.10
        assert pipeline.retrain_interval_days == 90
        assert pipeline.model_version == 1
        assert pipeline.new_outcomes_count == 0
        assert len(pipeline.outcome_buffer) == 0
    
    def test_initialization_with_custom_params(self, trained_models):
        """Test pipeline initializes with custom parameters"""
        pipeline = OnlineLearningPipeline(
            base_models=trained_models,
            update_threshold=100,
            rolling_window=500,
            validation_window=50,
            degradation_threshold=0.15,
            retrain_interval_days=60
        )
        
        assert pipeline.update_threshold == 100
        assert pipeline.rolling_window == 500
        assert pipeline.validation_window == 50
        assert pipeline.degradation_threshold == 0.15
        assert pipeline.retrain_interval_days == 60
    
    def test_models_copied_correctly(self, trained_models):
        """Test that models are copied to current_models"""
        pipeline = OnlineLearningPipeline(base_models=trained_models)
        
        assert 'random_forest' in pipeline.current_models
        assert 'gradient_boosting' in pipeline.current_models
        assert 'xgboost' in pipeline.current_models
        assert 'ensemble' in pipeline.current_models


class TestTradeOutcomeAccumulation:
    """Test trade outcome accumulation"""
    
    def test_accumulate_single_outcome(self, pipeline):
        """Test accumulating a single trade outcome"""
        features = {
            'ta_score': 75.0,
            'volume_spike': 0.8,
            'sentiment_score': 0.6,
            'volatility_percentile': 0.5,
            'trend_strength': 0.7
        }
        
        pipeline.accumulate_trade_outcome(features, outcome=True)
        
        assert len(pipeline.outcome_buffer) == 1
        assert pipeline.new_outcomes_count == 1
        assert pipeline.outcome_buffer[0]['outcome'] == True
        assert pipeline.outcome_buffer[0]['features'] == features
    
    def test_accumulate_multiple_outcomes(self, pipeline):
        """Test accumulating multiple trade outcomes"""
        for i in range(10):
            features = {'feature_' + str(j): float(i + j) for j in range(5)}
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        assert len(pipeline.outcome_buffer) == 10
        assert pipeline.new_outcomes_count == 10
    
    def test_rolling_window_limit(self, pipeline):
        """Test that buffer respects rolling window limit"""
        # Accumulate more than rolling_window trades
        for i in range(1200):
            features = {'feature': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        # Buffer should be limited to rolling_window size
        assert len(pipeline.outcome_buffer) == pipeline.rolling_window
        assert pipeline.new_outcomes_count == 1200


class TestUpdateTrigger:
    """Test update trigger logic"""
    
    def test_should_update_false_initially(self, pipeline):
        """Test should_update returns False initially"""
        assert pipeline.should_update() == False
    
    def test_should_update_false_below_threshold(self, pipeline):
        """Test should_update returns False below threshold"""
        for i in range(49):
            features = {'feature': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        assert pipeline.should_update() == False
    
    def test_should_update_true_at_threshold(self, pipeline):
        """Test should_update returns True at threshold"""
        for i in range(50):
            features = {'feature': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        assert pipeline.should_update() == True
    
    def test_should_update_true_above_threshold(self, pipeline):
        """Test should_update returns True above threshold"""
        for i in range(75):
            features = {'feature': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        assert pipeline.should_update() == True


class TestFullRetrainScheduling:
    """Test full retraining schedule logic"""
    
    def test_should_full_retrain_false_initially(self, pipeline):
        """Test should_full_retrain returns False initially"""
        assert pipeline.should_full_retrain() == False
    
    def test_should_full_retrain_after_interval(self, pipeline):
        """Test should_full_retrain returns True after interval"""
        # Set last_full_retrain to 91 days ago
        pipeline.last_full_retrain = datetime.now() - timedelta(days=91)
        
        assert pipeline.should_full_retrain() == True
    
    def test_schedule_full_retrain_info(self, pipeline):
        """Test schedule_full_retrain returns correct info"""
        schedule_info = pipeline.schedule_full_retrain()
        
        assert 'last_full_retrain' in schedule_info
        assert 'days_since_retrain' in schedule_info
        assert 'days_until_retrain' in schedule_info
        assert 'next_retrain_date' in schedule_info
        assert 'retrain_interval_days' in schedule_info
        assert 'should_retrain_now' in schedule_info
        
        assert schedule_info['retrain_interval_days'] == 90
        assert schedule_info['days_since_retrain'] >= 0
        assert schedule_info['days_until_retrain'] >= 0


class TestDataPreparation:
    """Test data preparation methods"""
    
    def test_prepare_training_data(self, pipeline):
        """Test preparing training data from buffer"""
        # Accumulate some outcomes
        for i in range(20):
            features = {
                'feature_1': float(i),
                'feature_2': float(i * 2),
                'feature_3': float(i * 3)
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        X_train, y_train = pipeline._prepare_training_data()
        
        assert isinstance(X_train, pd.DataFrame)
        assert isinstance(y_train, pd.Series)
        assert len(X_train) == 20
        assert len(y_train) == 20
        assert list(X_train.columns) == ['feature_1', 'feature_2', 'feature_3']
    
    def test_prepare_validation_data(self, pipeline):
        """Test preparing validation data from recent trades"""
        # Accumulate outcomes
        for i in range(150):
            features = {'feature': float(i)}
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        X_val, y_val = pipeline._prepare_validation_data()
        
        assert isinstance(X_val, pd.DataFrame)
        assert isinstance(y_val, pd.Series)
        assert len(X_val) == pipeline.validation_window
        assert len(y_val) == pipeline.validation_window
    
    def test_prepare_validation_data_small_buffer(self, pipeline):
        """Test validation data preparation with small buffer"""
        # Accumulate fewer outcomes than validation window
        for i in range(50):
            features = {'feature': float(i)}
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        X_val, y_val = pipeline._prepare_validation_data()
        
        # Should use all available data
        assert len(X_val) == 50
        assert len(y_val) == 50


class TestModelValidation:
    """Test model validation logic"""
    
    def test_validate_updated_model_with_similar_performance(self, pipeline):
        """Test validation passes when performance is similar"""
        # Accumulate outcomes
        for i in range(150):
            features = {
                'ta_score': 70.0 + i % 20,
                'volume_spike': 0.5 + (i % 10) * 0.05,
                'sentiment_score': 0.6,
                'volatility_percentile': 0.5,
                'trend_strength': 0.7
            }
            outcome = i % 3 != 0  # ~67% success rate
            pipeline.accumulate_trade_outcome(features, outcome)
        
        # Current models should validate successfully (same models)
        validation_passed = pipeline.validate_updated_model(pipeline.current_models)
        
        # Should pass since it's the same model
        assert validation_passed == True
    
    def test_validation_stores_performance_history(self, pipeline):
        """Test that validation stores performance metrics"""
        # Accumulate outcomes with correct feature names
        for i in range(150):
            features = {
                'ta_score': 70.0 + (i % 20),
                'volume_spike': 0.5 + (i % 10) * 0.05,
                'sentiment_score': 0.6,
                'volatility_percentile': 0.5,
                'trend_strength': 0.7
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        initial_history_len = len(pipeline.performance_history)
        
        pipeline.validate_updated_model(pipeline.current_models)
        
        assert len(pipeline.performance_history) == initial_history_len + 1
        
        latest_metrics = pipeline.performance_history[-1]
        assert 'timestamp' in latest_metrics
        assert 'model_version' in latest_metrics
        assert 'prev_accuracy' in latest_metrics
        assert 'new_accuracy' in latest_metrics
        assert 'performance_change' in latest_metrics
        assert 'degradation' in latest_metrics


class TestModelRollback:
    """Test model rollback functionality"""
    
    def test_rollback_with_no_previous_models(self, pipeline):
        """Test rollback when no previous models exist"""
        # Should not raise error
        pipeline.rollback_model()
        
        # Models should remain unchanged
        assert pipeline.current_models is not None
    
    def test_rollback_restores_previous_models(self, pipeline, trained_models):
        """Test rollback restores previous model version"""
        # Store original models
        original_models = pipeline.current_models
        
        # Create "new" models (just copies for testing)
        new_models = {k: v for k, v in trained_models.items()}
        pipeline.previous_models = original_models
        pipeline.current_models = new_models
        
        # Rollback
        pipeline.rollback_model()
        
        # Should restore original models
        assert pipeline.current_models == original_models
        assert pipeline.previous_models is None


class TestPipelineStatus:
    """Test pipeline status reporting"""
    
    def test_get_status(self, pipeline):
        """Test get_status returns correct information"""
        status = pipeline.get_status()
        
        assert 'model_version' in status
        assert 'last_update_time' in status
        assert 'last_full_retrain' in status
        assert 'buffer_size' in status
        assert 'new_outcomes_count' in status
        assert 'update_threshold' in status
        assert 'should_update' in status
        assert 'should_full_retrain' in status
        assert 'performance_history_length' in status
        
        assert status['model_version'] == 1
        assert status['buffer_size'] == 0
        assert status['new_outcomes_count'] == 0
        assert status['update_threshold'] == 50
    
    def test_get_current_models(self, pipeline):
        """Test get_current_models returns models"""
        models = pipeline.get_current_models()
        
        assert 'random_forest' in models
        assert 'gradient_boosting' in models
        assert 'xgboost' in models
        assert 'ensemble' in models


class TestFullRetrainCompletion:
    """Test full retrain completion"""
    
    def test_mark_full_retrain_complete(self, pipeline, trained_models):
        """Test marking full retrain as complete"""
        initial_version = pipeline.model_version
        initial_retrain_date = pipeline.last_full_retrain
        
        # Create new models
        new_models = {k: v for k, v in trained_models.items()}
        
        # Mark retrain complete
        pipeline.mark_full_retrain_complete(new_models)
        
        assert pipeline.model_version == initial_version + 1
        assert pipeline.last_full_retrain > initial_retrain_date
        assert pipeline.current_models == new_models
        assert pipeline.base_models == new_models
        assert pipeline.previous_models is None


class TestIncrementalUpdate:
    """Test incremental update process"""
    
    @pytest.mark.asyncio
    async def test_incremental_update_with_sufficient_data(self, pipeline):
        """Test incremental update with sufficient training data"""
        # Accumulate sufficient outcomes
        for i in range(200):
            features = {
                'ta_score': 60.0 + (i % 30),
                'volume_spike': 0.3 + (i % 10) * 0.07,
                'sentiment_score': 0.5 + (i % 5) * 0.1,
                'volatility_percentile': 0.4 + (i % 6) * 0.1,
                'trend_strength': 0.6 + (i % 4) * 0.1
            }
            outcome = i % 3 != 0  # ~67% success rate
            pipeline.accumulate_trade_outcome(features, outcome)
        
        initial_version = pipeline.model_version
        
        # Perform incremental update
        result = await pipeline.incremental_update()
        
        assert 'success' in result
        assert 'model_version' in result
        assert 'training_samples' in result
        assert 'validation_passed' in result
        
        # Version should increment if successful
        if result['success']:
            assert pipeline.model_version == initial_version + 1
            assert pipeline.new_outcomes_count == 0  # Should reset
    
    @pytest.mark.asyncio
    async def test_incremental_update_resets_counter_on_success(self, pipeline):
        """Test that new_outcomes_count resets after successful update"""
        # Accumulate outcomes
        for i in range(200):
            features = {
                'ta_score': 70.0,
                'volume_spike': 0.8,
                'sentiment_score': 0.6,
                'volatility_percentile': 0.5,
                'trend_strength': 0.7
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        assert pipeline.new_outcomes_count == 200
        
        result = await pipeline.incremental_update()
        
        if result['success']:
            assert pipeline.new_outcomes_count == 0


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_prepare_training_data_empty_buffer(self, pipeline):
        """Test preparing training data with empty buffer raises error"""
        with pytest.raises(ValueError, match="Outcome buffer is empty"):
            pipeline._prepare_training_data()
    
    def test_accumulate_with_missing_features(self, pipeline):
        """Test accumulating outcome with incomplete features"""
        # Should not raise error - just stores what's provided
        features = {'only_one_feature': 1.0}
        pipeline.accumulate_trade_outcome(features, outcome=True)
        
        assert len(pipeline.outcome_buffer) == 1
    
    def test_validation_with_zero_previous_accuracy(self, pipeline):
        """Test validation handles zero previous accuracy"""
        # This is an edge case that shouldn't normally occur
        # but the code should handle it gracefully
        
        # Accumulate some outcomes with correct feature names
        for i in range(150):
            features = {
                'ta_score': 70.0,
                'volume_spike': 0.8,
                'sentiment_score': 0.6,
                'volatility_percentile': 0.5,
                'trend_strength': 0.7
            }
            outcome = False  # All failures
            pipeline.accumulate_trade_outcome(features, outcome)
        
        # Validation should not crash
        try:
            result = pipeline.validate_updated_model(pipeline.current_models)
            # Should return a boolean
            assert isinstance(result, bool)
        except Exception as e:
            pytest.fail(f"Validation raised unexpected exception: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
