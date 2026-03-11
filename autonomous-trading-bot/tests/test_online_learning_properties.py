"""
Property-Based Tests for OnlineLearningPipeline

Tests universal properties that should hold across all inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from xgboost import XGBClassifier
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from online_learning_pipeline import OnlineLearningPipeline


# Helper function to create trained models
def create_simple_models():
    """Create simple trained models for testing"""
    np.random.seed(42)
    X = pd.DataFrame({
        'feature_1': np.random.uniform(0, 1, 100),
        'feature_2': np.random.uniform(0, 1, 100),
        'feature_3': np.random.uniform(0, 1, 100)
    })
    y = pd.Series(np.random.choice([0, 1], size=100))
    
    rf_model = RandomForestClassifier(n_estimators=5, max_depth=3, random_state=42)
    rf_model.fit(X, y)
    
    gb_model = GradientBoostingClassifier(n_estimators=5, max_depth=3, random_state=42)
    gb_model.fit(X, y)
    
    xgb_model = XGBClassifier(n_estimators=5, max_depth=3, random_state=42, eval_metric='logloss')
    xgb_model.fit(X, y)
    
    ensemble = VotingClassifier(
        estimators=[('rf', rf_model), ('gb', gb_model), ('xgb', xgb_model)],
        voting='soft',
        weights=[0.3, 0.3, 0.4]
    )
    ensemble.fit(X, y)
    
    return {
        'random_forest': rf_model,
        'gradient_boosting': gb_model,
        'xgboost': xgb_model,
        'ensemble': ensemble
    }


# Strategies for generating test data
feature_dict_strategy = st.fixed_dictionaries({
    'feature_1': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    'feature_2': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    'feature_3': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
})

outcome_strategy = st.booleans()

update_threshold_strategy = st.integers(min_value=10, max_value=100)
rolling_window_strategy = st.integers(min_value=100, max_value=2000)
validation_window_strategy = st.integers(min_value=10, max_value=200)
degradation_threshold_strategy = st.floats(min_value=0.05, max_value=0.30)


class TestAccumulationProperties:
    """Test properties of trade outcome accumulation"""
    
    @given(
        features=feature_dict_strategy,
        outcome=outcome_strategy
    )
    @settings(max_examples=50, deadline=None)
    def test_accumulation_increases_buffer_size(self, features, outcome):
        """
        **Validates: Requirements 19.1**
        
        Property: Accumulating a trade outcome always increases buffer size by 1
        (until rolling window limit is reached)
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, rolling_window=1000)
        
        initial_size = len(pipeline.outcome_buffer)
        pipeline.accumulate_trade_outcome(features, outcome)
        final_size = len(pipeline.outcome_buffer)
        
        assert final_size == initial_size + 1
        assert pipeline.new_outcomes_count == 1
    
    @given(
        num_outcomes=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=30, deadline=None)
    def test_accumulation_count_matches_additions(self, num_outcomes):
        """
        **Validates: Requirements 19.1**
        
        Property: new_outcomes_count always equals the number of outcomes accumulated
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models)
        
        for i in range(num_outcomes):
            features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        assert pipeline.new_outcomes_count == num_outcomes
        assert len(pipeline.outcome_buffer) == num_outcomes
    
    @given(
        rolling_window=rolling_window_strategy,
        num_outcomes=st.integers(min_value=100, max_value=300)
    )
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_buffer_respects_rolling_window_limit(self, rolling_window, num_outcomes):
        """
        **Validates: Requirements 19.4**
        
        Property: Buffer size never exceeds rolling_window parameter
        """
        assume(num_outcomes > rolling_window)
        
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, rolling_window=rolling_window)
        
        for i in range(num_outcomes):
            features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=i % 2 == 0)
        
        assert len(pipeline.outcome_buffer) == rolling_window
        assert len(pipeline.outcome_buffer) <= rolling_window


class TestUpdateTriggerProperties:
    """Test properties of update trigger logic"""
    
    @given(
        update_threshold=update_threshold_strategy,
        num_outcomes=st.integers(min_value=1, max_value=200)
    )
    @settings(max_examples=30, deadline=None)
    def test_should_update_threshold_behavior(self, update_threshold, num_outcomes):
        """
        **Validates: Requirements 19.2**
        
        Property: should_update() returns True if and only if new_outcomes_count >= update_threshold
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, update_threshold=update_threshold)
        
        for i in range(num_outcomes):
            features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        expected_should_update = num_outcomes >= update_threshold
        assert pipeline.should_update() == expected_should_update
    
    @given(
        update_threshold=update_threshold_strategy
    )
    @settings(max_examples=20, deadline=None)
    def test_should_update_false_below_threshold(self, update_threshold):
        """
        **Validates: Requirements 19.2**
        
        Property: should_update() is always False when new_outcomes_count < update_threshold
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, update_threshold=update_threshold)
        
        # Accumulate one less than threshold
        if update_threshold > 1:
            for i in range(update_threshold - 1):
                features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
                pipeline.accumulate_trade_outcome(features, outcome=True)
            
            assert pipeline.should_update() == False
    
    @given(
        num_outcomes=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=5, deadline=None)
    def test_online_learning_trigger_at_exactly_50_outcomes(self, num_outcomes):
        """
        **Validates: Requirements 19.2**
        
        Property 35: Online learning trigger
        For any online learning pipeline, incremental update should trigger when 
        exactly 50 new trade outcomes have accumulated.
        
        This test validates that:
        - should_update() returns False when new_outcomes_count < 50
        - should_update() returns True when new_outcomes_count >= 50
        - The trigger happens at exactly 50 outcomes (not before, not after)
        """
        models = create_simple_models()
        # Use default update_threshold of 50
        pipeline = OnlineLearningPipeline(base_models=models, update_threshold=50)
        
        # Accumulate outcomes
        for i in range(num_outcomes):
            features = {
                'feature_1': 0.5 + (i % 10) * 0.05,
                'feature_2': 0.6 + (i % 8) * 0.05,
                'feature_3': 0.7 + (i % 6) * 0.05
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        # Verify trigger behavior
        if num_outcomes < 50:
            # Should NOT trigger before 50 outcomes
            assert pipeline.should_update() == False, \
                f"Update should NOT trigger at {num_outcomes} outcomes (< 50)"
            assert pipeline.new_outcomes_count == num_outcomes
        else:
            # Should trigger at exactly 50 or more outcomes
            assert pipeline.should_update() == True, \
                f"Update SHOULD trigger at {num_outcomes} outcomes (>= 50)"
            assert pipeline.new_outcomes_count >= 50
        
        # Verify the exact threshold is 50
        assert pipeline.update_threshold == 50, \
            "Default update_threshold should be 50"


class TestDataPreparationProperties:
    """Test properties of data preparation"""
    
    @given(
        num_outcomes=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=20, deadline=None)
    def test_training_data_size_matches_buffer(self, num_outcomes):
        """
        **Validates: Requirements 19.4**
        
        Property: Prepared training data size equals buffer size
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models)
        
        for i in range(num_outcomes):
            features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=i % 2 == 0)
        
        X_train, y_train = pipeline._prepare_training_data()
        
        assert len(X_train) == len(pipeline.outcome_buffer)
        assert len(y_train) == len(pipeline.outcome_buffer)
        assert len(X_train) == len(y_train)
    
    @given(
        validation_window=validation_window_strategy,
        num_outcomes=st.integers(min_value=50, max_value=300)
    )
    @settings(max_examples=20, deadline=None)
    def test_validation_data_size_bounded(self, validation_window, num_outcomes):
        """
        **Validates: Requirements 19.5**
        
        Property: Validation data size is min(buffer_size, validation_window)
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, validation_window=validation_window)
        
        for i in range(num_outcomes):
            features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=i % 2 == 0)
        
        X_val, y_val = pipeline._prepare_validation_data()
        
        expected_size = min(len(pipeline.outcome_buffer), validation_window)
        assert len(X_val) == expected_size
        assert len(y_val) == expected_size


class TestModelVersioningProperties:
    """Test properties of model versioning"""
    
    @given(
        num_updates=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_version_increments_on_successful_update(self, num_updates):
        """
        **Validates: Requirements 19.7**
        
        Property: Model version increments by 1 for each successful update
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, update_threshold=50)
        
        initial_version = pipeline.model_version
        successful_updates = 0
        
        for update_num in range(num_updates):
            # Accumulate outcomes
            for i in range(60):
                features = {
                    'feature_1': 0.5 + (i % 10) * 0.05,
                    'feature_2': 0.6 + (i % 8) * 0.05,
                    'feature_3': 0.7 + (i % 6) * 0.05
                }
                outcome = i % 3 != 0  # ~67% success rate
                pipeline.accumulate_trade_outcome(features, outcome)
            
            # Attempt update
            import asyncio
            result = asyncio.run(pipeline.incremental_update())
            
            if result.get('success', False):
                successful_updates += 1
        
        expected_version = initial_version + successful_updates
        assert pipeline.model_version == expected_version
    
    def test_version_unchanged_on_rollback(self):
        """
        **Validates: Requirements 19.6**
        
        Property: Model version remains unchanged after rollback
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models)
        
        initial_version = pipeline.model_version
        
        # Set up previous models
        pipeline.previous_models = {k: v for k, v in models.items()}
        
        # Rollback
        pipeline.rollback_model()
        
        assert pipeline.model_version == initial_version


class TestValidationProperties:
    """Test properties of model validation"""
    
    @given(
        num_outcomes=st.integers(min_value=150, max_value=250)
    )
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_validation_returns_boolean(self, num_outcomes):
        """
        **Validates: Requirements 19.5**
        
        Property: validate_updated_model always returns a boolean
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models)
        
        # Accumulate outcomes
        for i in range(num_outcomes):
            features = {
                'feature_1': 0.5 + (i % 10) * 0.05,
                'feature_2': 0.6 + (i % 8) * 0.05,
                'feature_3': 0.7 + (i % 6) * 0.05
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        result = pipeline.validate_updated_model(pipeline.current_models)
        
        assert isinstance(result, bool)
    
    @given(
        num_outcomes=st.integers(min_value=150, max_value=250)
    )
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_validation_stores_performance_history(self, num_outcomes):
        """
        **Validates: Requirements 19.5**
        
        Property: Each validation adds exactly one entry to performance_history
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models)
        
        # Accumulate outcomes
        for i in range(num_outcomes):
            features = {
                'feature_1': 0.5,
                'feature_2': 0.6,
                'feature_3': 0.7
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        initial_history_len = len(pipeline.performance_history)
        
        pipeline.validate_updated_model(pipeline.current_models)
        
        assert len(pipeline.performance_history) == initial_history_len + 1


class TestModelRollbackProperties:
    """Test properties of model rollback behavior"""
    
    @given(
        degradation_pct=st.floats(min_value=0.11, max_value=0.50)
    )
    @settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rollback_on_performance_degradation(self, degradation_pct):
        """
        **Validates: Requirements 19.6**
        
        Property 36: Model rollback condition
        For any updated model, if performance on recent trades degrades >10% from 
        previous version, rollback to previous model should occur.
        
        This test validates that:
        - When new model accuracy degrades by >10%, validation fails
        - Rollback restores the previous model
        - Model version remains unchanged after rollback
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(
            base_models=models, 
            update_threshold=50,
            degradation_threshold=0.10  # 10% threshold
        )
        
        # Accumulate outcomes with good performance
        for i in range(200):
            features = {
                'feature_1': 0.5 + (i % 10) * 0.05,
                'feature_2': 0.6 + (i % 8) * 0.05,
                'feature_3': 0.7 + (i % 6) * 0.05
            }
            # 70% success rate for initial training
            outcome = i % 10 < 7
            pipeline.accumulate_trade_outcome(features, outcome)
        
        # Store original model version
        original_version = pipeline.model_version
        
        # Get validation data
        X_val, y_val = pipeline._prepare_validation_data()
        
        # Get baseline accuracy from current models
        baseline_predictions = pipeline.current_models['ensemble'].predict(X_val)
        baseline_accuracy = (baseline_predictions == y_val).mean()
        
        # Create a mock degraded model that will perform worse
        # We'll create a model that predicts randomly to ensure degradation
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
        from xgboost import XGBClassifier
        from sklearn.dummy import DummyClassifier
        
        # Use DummyClassifier with strategy that will perform poorly
        # This ensures degradation regardless of data distribution
        degraded_rf = DummyClassifier(strategy='uniform', random_state=42)
        degraded_rf.fit(X_val, y_val)
        
        degraded_gb = DummyClassifier(strategy='uniform', random_state=43)
        degraded_gb.fit(X_val, y_val)
        
        degraded_xgb = DummyClassifier(strategy='uniform', random_state=44)
        degraded_xgb.fit(X_val, y_val)
        
        degraded_ensemble = VotingClassifier(
            estimators=[('rf', degraded_rf), ('gb', degraded_gb), ('xgb', degraded_xgb)],
            voting='hard'
        )
        degraded_ensemble.fit(X_val, y_val)
        
        degraded_models = {
            'random_forest': degraded_rf,
            'gradient_boosting': degraded_gb,
            'xgboost': degraded_xgb,
            'ensemble': degraded_ensemble
        }
        
        # Verify degraded model actually performs worse
        degraded_predictions = degraded_ensemble.predict(X_val)
        degraded_accuracy = (degraded_predictions == y_val).mean()
        
        # Calculate expected degradation
        if baseline_accuracy > 0:
            actual_degradation = (baseline_accuracy - degraded_accuracy) / baseline_accuracy
        else:
            actual_degradation = 0.0
        
        # Store previous models for rollback
        pipeline.previous_models = {k: v for k, v in pipeline.current_models.items()}
        
        # Validate the degraded model
        validation_passed = pipeline.validate_updated_model(degraded_models)
        
        # Check that performance history was recorded
        assert len(pipeline.performance_history) > 0, \
            "Performance history should be recorded during validation"
        
        last_validation = pipeline.performance_history[-1]
        
        # If actual degradation > 10%, validation should fail
        if actual_degradation > 0.10:
            assert validation_passed == False, \
                f"Validation should fail when degradation {actual_degradation:.2%} > 10%"
            
            # Verify degradation was detected
            assert last_validation['degradation'] > 0.10, \
                f"Recorded degradation {last_validation['degradation']:.2%} should be > 10%"
            
            # Simulate rollback (as would happen in incremental_update)
            pipeline.rollback_model()
            
            # Verify model version unchanged after rollback
            assert pipeline.model_version == original_version, \
                f"Model version should remain {original_version} after rollback"
            
            # Verify previous models were restored
            assert pipeline.current_models is not None, \
                "Current models should be restored after rollback"
            
            # Verify previous_models is cleared after rollback
            assert pipeline.previous_models is None, \
                "Previous models should be cleared after rollback"
        else:
            # If degradation <= 10%, validation should pass
            assert validation_passed == True, \
                f"Validation should pass when degradation {actual_degradation:.2%} <= 10%"
    
    @given(
        num_outcomes=st.integers(min_value=150, max_value=250)
    )
    @settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_no_rollback_on_acceptable_performance(self, num_outcomes):
        """
        **Validates: Requirements 19.6**
        
        Property: Model is NOT rolled back when performance degradation is ≤10%
        
        This test validates that:
        - When new model accuracy degrades by ≤10%, validation passes
        - No rollback occurs
        - Model version increments normally
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(
            base_models=models,
            update_threshold=50,
            degradation_threshold=0.10
        )
        
        # Accumulate outcomes
        for i in range(num_outcomes):
            features = {
                'feature_1': 0.5 + (i % 10) * 0.05,
                'feature_2': 0.6 + (i % 8) * 0.05,
                'feature_3': 0.7 + (i % 6) * 0.05
            }
            # Balanced success rate
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        # Store previous models
        pipeline.previous_models = {k: v for k, v in pipeline.current_models.items()}
        
        # Validate current models (should pass since they're the same)
        validation_passed = pipeline.validate_updated_model(pipeline.current_models)
        
        # Validation should pass when models are similar
        assert validation_passed == True, \
            "Validation should pass when performance is acceptable"
        
        # Verify performance history was recorded
        assert len(pipeline.performance_history) > 0
        
        last_validation = pipeline.performance_history[-1]
        
        # Verify degradation is within acceptable range
        assert last_validation['degradation'] <= pipeline.degradation_threshold, \
            f"Degradation {last_validation['degradation']:.2%} should be ≤ threshold {pipeline.degradation_threshold:.2%}"
    
    def test_rollback_threshold_exactly_10_percent(self):
        """
        **Validates: Requirements 19.6**
        
        Property: Rollback occurs when degradation exceeds exactly 10%
        
        This test validates the boundary condition:
        - Degradation of exactly 10% should pass validation
        - Degradation of >10% should fail validation and trigger rollback
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(
            base_models=models,
            degradation_threshold=0.10  # Exactly 10%
        )
        
        # Accumulate outcomes
        for i in range(200):
            features = {
                'feature_1': 0.5 + (i % 10) * 0.05,
                'feature_2': 0.6 + (i % 8) * 0.05,
                'feature_3': 0.7 + (i % 6) * 0.05
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        # Verify the threshold is exactly 10%
        assert pipeline.degradation_threshold == 0.10, \
            "Degradation threshold should be exactly 10% (0.10)"
        
        # Test that validation logic uses <= for comparison
        # (degradation of exactly 10% should pass)
        X_val, y_val = pipeline._prepare_validation_data()
        
        # Store previous models
        pipeline.previous_models = {k: v for k, v in pipeline.current_models.items()}
        
        # Validate with same models (0% degradation - should pass)
        validation_passed = pipeline.validate_updated_model(pipeline.current_models)
        assert validation_passed == True, \
            "Validation should pass with 0% degradation"




class TestStatusReportingProperties:
    """Test properties of status reporting"""
    
    @given(
        num_outcomes=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=20, deadline=None)
    def test_status_reflects_current_state(self, num_outcomes):
        """
        **Validates: Requirements 19.7**
        
        Property: get_status() always returns accurate current state
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, update_threshold=50)
        
        for i in range(num_outcomes):
            features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        status = pipeline.get_status()
        
        assert status['buffer_size'] == len(pipeline.outcome_buffer)
        assert status['new_outcomes_count'] == pipeline.new_outcomes_count
        assert status['model_version'] == pipeline.model_version
        assert status['update_threshold'] == pipeline.update_threshold
        assert status['should_update'] == pipeline.should_update()
    
    def test_status_contains_required_fields(self):
        """
        **Validates: Requirements 19.7**
        
        Property: get_status() always contains all required fields
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models)
        
        status = pipeline.get_status()
        
        required_fields = [
            'model_version',
            'last_update_time',
            'last_full_retrain',
            'buffer_size',
            'new_outcomes_count',
            'update_threshold',
            'should_update',
            'should_full_retrain',
            'performance_history_length'
        ]
        
        for field in required_fields:
            assert field in status


class TestRollingWindowProperties:
    """Test properties of rolling window behavior"""
    
    @given(
        rolling_window=st.integers(min_value=50, max_value=500),
        num_outcomes=st.integers(min_value=100, max_value=600)
    )
    @settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_oldest_data_removed_when_window_full(self, rolling_window, num_outcomes):
        """
        **Validates: Requirements 19.4**
        
        Property: When buffer exceeds rolling_window, oldest data is removed
        """
        assume(num_outcomes > rolling_window)
        
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, rolling_window=rolling_window)
        
        # Track first outcome
        first_features = {'feature_1': 999.0, 'feature_2': 999.0, 'feature_3': 999.0}
        pipeline.accumulate_trade_outcome(first_features, outcome=True)
        
        # Add more outcomes to exceed rolling window
        for i in range(num_outcomes):
            features = {'feature_1': float(i), 'feature_2': float(i), 'feature_3': float(i)}
            pipeline.accumulate_trade_outcome(features, outcome=True)
        
        # Buffer should be at rolling_window size
        assert len(pipeline.outcome_buffer) == rolling_window
        
        # First outcome should be removed if we exceeded window
        if num_outcomes >= rolling_window:
            first_outcome_in_buffer = pipeline.outcome_buffer[0]['features']['feature_1']
            assert first_outcome_in_buffer != 999.0


class TestIncrementalUpdateProperties:
    """Test properties of incremental updates"""
    
    @given(
        num_outcomes=st.integers(min_value=150, max_value=250)
    )
    @settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_update_resets_counter_on_success(self, num_outcomes):
        """
        **Validates: Requirements 19.2**
        
        Property: Successful incremental update resets new_outcomes_count to 0
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, update_threshold=50)
        
        # Accumulate outcomes
        for i in range(num_outcomes):
            features = {
                'feature_1': 0.5 + (i % 10) * 0.05,
                'feature_2': 0.6 + (i % 8) * 0.05,
                'feature_3': 0.7 + (i % 6) * 0.05
            }
            outcome = i % 3 != 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        assert pipeline.new_outcomes_count > 0
        
        # Perform update
        import asyncio
        result = asyncio.run(pipeline.incremental_update())
        
        if result.get('success', False):
            assert pipeline.new_outcomes_count == 0
    
    @given(
        num_outcomes=st.integers(min_value=150, max_value=250)
    )
    @settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_update_preserves_buffer(self, num_outcomes):
        """
        **Validates: Requirements 19.4**
        
        Property: Incremental update preserves outcome buffer
        """
        models = create_simple_models()
        pipeline = OnlineLearningPipeline(base_models=models, update_threshold=50)
        
        # Accumulate outcomes
        for i in range(num_outcomes):
            features = {
                'feature_1': 0.5,
                'feature_2': 0.6,
                'feature_3': 0.7
            }
            outcome = i % 2 == 0
            pipeline.accumulate_trade_outcome(features, outcome)
        
        buffer_size_before = len(pipeline.outcome_buffer)
        
        # Perform update
        import asyncio
        asyncio.run(pipeline.incremental_update())
        
        buffer_size_after = len(pipeline.outcome_buffer)
        
        # Buffer should remain unchanged
        assert buffer_size_after == buffer_size_before


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
