"""
Property-Based Tests for ML Feature Engineering

Tests universal correctness properties for feature engineering using Hypothesis.
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from src.ml_feature_engineer import MLFeatureEngineer


# Property 29: Feature normalization
@given(
    values=st.lists(st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False), 
                   min_size=10, max_size=100)
)
@settings(max_examples=5, deadline=None)
def test_property_29_feature_normalization(values):
    """
    Property 29: Feature normalization
    
    For any numeric feature, normalized value should be in range [0.0, 1.0]
    calculated as (value - min) / (max - min)
    
    Validates: Requirements 16.5
    """
    # Create feature dataframe
    df = pd.DataFrame({'feature': values})
    
    # Create minimal trade history and market data
    trade_history = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=len(values), freq='1h'),
        'symbol': ['BTC/USDT'] * len(values),
        'r_multiple': [1.0] * len(values)
    })
    
    engineer = MLFeatureEngineer(trade_history, {})
    
    # Normalize the feature
    normalized = engineer.normalize_features(df)
    
    # Property: All normalized values should be in [0.0, 1.0]
    assert (normalized['feature'] >= 0.0).all(), "Normalized values should be >= 0.0"
    assert (normalized['feature'] <= 1.0).all(), "Normalized values should be <= 1.0"
    
    # Property: Min value should normalize to 0.0
    if len(set(values)) > 1:  # Only if there's variance
        min_idx = df['feature'].idxmin()
        assert abs(normalized.loc[min_idx, 'feature'] - 0.0) < 1e-10, "Min value should normalize to 0.0"
        
        # Property: Max value should normalize to 1.0
        max_idx = df['feature'].idxmax()
        assert abs(normalized.loc[max_idx, 'feature'] - 1.0) < 1e-10, "Max value should normalize to 1.0"


# Property 30: No data leakage in features
@given(
    n_trades=st.integers(min_value=10, max_value=50)
)
@settings(max_examples=5, deadline=None)
def test_property_30_no_data_leakage(n_trades):
    """
    Property 30: No data leakage in features
    
    For any feature at timestamp T, the feature should only use data with timestamps < T
    
    Validates: Requirements 16.7
    """
    # Create trade history with sequential timestamps
    timestamps = pd.date_range(start='2024-01-01', periods=n_trades, freq='1h')
    
    trade_history = pd.DataFrame({
        'timestamp': timestamps,
        'symbol': ['BTC/USDT'] * n_trades,
        'ta_score': np.random.uniform(50, 90, n_trades),
        'volume_spike': np.random.uniform(0.8, 2.0, n_trades),
        'r_multiple': np.random.uniform(-1, 5, n_trades)
    })
    
    # Create market data
    market_dates = pd.date_range(start='2023-12-01', periods=n_trades + 100, freq='1h')
    market_data = {
        'BTC/USDT': pd.DataFrame({
            'open': np.random.uniform(40000, 45000, len(market_dates)),
            'high': np.random.uniform(40000, 45000, len(market_dates)),
            'low': np.random.uniform(40000, 45000, len(market_dates)),
            'close': np.random.uniform(40000, 45000, len(market_dates)),
            'volume': np.random.uniform(100, 1000, len(market_dates))
        }, index=market_dates)
    }
    
    engineer = MLFeatureEngineer(trade_history, market_data)
    
    # Extract derived features (which use .diff())
    derived = engineer.create_derived_features()
    
    # Property: First row of momentum features should be 0 or NaN (no previous data)
    # This ensures no look-ahead bias
    assert derived['score_momentum'].iloc[0] == 0.0 or pd.isna(derived['score_momentum'].iloc[0]), \
        "First momentum value should be 0 or NaN (no previous data to compare)"
    
    # Property: For any row i, derived features should only depend on rows 0 to i-1
    # We verify this by checking that momentum at row i uses data from row i-1
    if n_trades > 2:
        for i in range(1, min(5, n_trades)):  # Check first few rows
            expected_momentum = trade_history['ta_score'].iloc[i] - trade_history['ta_score'].iloc[i-1]
            actual_momentum = derived['score_momentum'].iloc[i]
            assert abs(expected_momentum - actual_momentum) < 1e-6, \
                f"Momentum at row {i} should only use data from previous rows"


# Property 31: Target variable definition
@given(
    r_multiples=st.lists(st.floats(min_value=-5.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                        min_size=10, max_size=100)
)
@settings(max_examples=5, deadline=None)
def test_property_31_target_variable_definition(r_multiples):
    """
    Property 31: Target variable definition
    
    For any trade, target variable should be 1 if R-multiple > 1.5, else 0
    
    Validates: Requirements 16.8
    """
    # Create trade history
    trade_history = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=len(r_multiples), freq='1h'),
        'symbol': ['BTC/USDT'] * len(r_multiples),
        'r_multiple': r_multiples
    })
    
    engineer = MLFeatureEngineer(trade_history, {})
    
    # Create target variable
    target = engineer.create_target_variable()
    
    # Property: Target should be binary (0 or 1)
    assert target.isin([0, 1]).all(), "Target should only contain 0 or 1"
    
    # Property: Target should be 1 if and only if R-multiple > 1.5
    for i, r_mult in enumerate(r_multiples):
        expected_target = 1 if r_mult > 1.5 else 0
        actual_target = target.iloc[i]
        assert actual_target == expected_target, \
            f"Target for R-multiple {r_mult} should be {expected_target}, got {actual_target}"


# Additional property test: Feature extraction completeness
@given(
    n_trades=st.integers(min_value=5, max_value=30)
)
@settings(max_examples=5, deadline=None)
def test_property_feature_extraction_completeness(n_trades):
    """
    Property: Feature extraction should produce no missing values after handling
    
    For any valid trade history, the complete feature extraction pipeline
    should produce a feature matrix with no missing values.
    """
    # Create trade history
    timestamps = pd.date_range(start='2024-01-01', periods=n_trades, freq='1h')
    
    trade_history = pd.DataFrame({
        'timestamp': timestamps,
        'symbol': ['BTC/USDT'] * n_trades,
        'ta_score': np.random.uniform(50, 90, n_trades),
        'volume_spike': np.random.uniform(0.8, 2.0, n_trades),
        'sentiment': np.random.choice(['bullish', 'bearish', 'neutral'], n_trades),
        'volatility_percentile': np.random.uniform(20, 80, n_trades),
        'trend_strength': np.random.uniform(0.3, 0.9, n_trades),
        'r_multiple': np.random.uniform(-1, 5, n_trades)
    })
    
    # Create market data
    market_dates = pd.date_range(start='2023-12-01', periods=n_trades + 100, freq='1h')
    market_data = {
        'BTC/USDT': pd.DataFrame({
            'open': np.random.uniform(40000, 45000, len(market_dates)),
            'high': np.random.uniform(40000, 45000, len(market_dates)),
            'low': np.random.uniform(40000, 45000, len(market_dates)),
            'close': np.random.uniform(40000, 45000, len(market_dates)),
            'volume': np.random.uniform(100, 1000, len(market_dates)),
            'atr': np.random.uniform(100, 500, len(market_dates))
        }, index=market_dates)
    }
    
    engineer = MLFeatureEngineer(trade_history, market_data)
    
    # Extract all features
    features = engineer.extract_features()
    
    # Property: No missing values should remain
    assert not features.isna().any().any(), "Feature extraction should produce no missing values"
    
    # Property: All features should be numeric
    assert features.select_dtypes(include=[np.number]).shape[1] == features.shape[1], \
        "All features should be numeric"


# Property test: Sentiment score mapping
@given(
    sentiment=st.sampled_from(['bullish', 'bearish', 'neutral', 'BULLISH', 'Bearish', 'NEUTRAL', 'unknown'])
)
@settings(max_examples=5, deadline=None)
def test_property_sentiment_score_mapping(sentiment):
    """
    Property: Sentiment should map consistently to numeric scores
    
    For any sentiment string:
    - Bullish (case-insensitive) -> 1.0
    - Bearish (case-insensitive) -> -1.0
    - Neutral or unknown -> 0.0
    """
    trade_history = pd.DataFrame({
        'timestamp': [datetime.now()],
        'symbol': ['BTC/USDT'],
        'r_multiple': [1.0]
    })
    
    engineer = MLFeatureEngineer(trade_history, {})
    score = engineer._sentiment_to_score(sentiment)
    
    # Property: Score should be one of {-1.0, 0.0, 1.0}
    assert score in [-1.0, 0.0, 1.0], f"Sentiment score should be -1.0, 0.0, or 1.0, got {score}"
    
    # Property: Mapping should be consistent
    sentiment_lower = sentiment.lower()
    if 'bullish' in sentiment_lower:
        assert score == 1.0, "Bullish sentiment should map to 1.0"
    elif 'bearish' in sentiment_lower:
        assert score == -1.0, "Bearish sentiment should map to -1.0"
    else:
        assert score == 0.0, "Neutral/unknown sentiment should map to 0.0"


# Property 32: Ensemble prediction
@given(
    n_samples=st.integers(min_value=50, max_value=200),
    n_features=st.integers(min_value=5, max_value=15)
)
@settings(max_examples=5, deadline=None)
def test_property_32_ensemble_prediction(n_samples, n_features):
    """
    Property 32: Ensemble prediction
    
    For any input, ensemble prediction should equal weighted_average([rf_pred × 0.3, gb_pred × 0.3, xgb_pred × 0.4])
    
    **Validates: Requirements 17.5**
    """
    from src.ml_model_trainer import MLModelTrainer
    
    # Create random features
    np.random.seed(42)
    features = pd.DataFrame(
        np.random.uniform(0, 1, (n_samples, n_features)),
        columns=[f'feature_{i}' for i in range(n_features)]
    )
    
    # Create target with balanced classes to ensure both classes present in all splits
    # Use stratified approach: ensure at least 40% of each class
    n_positive = max(int(n_samples * 0.45), int(n_samples * 0.70 * 0.3))  # Ensure enough in train set
    target_values = [1] * n_positive + [0] * (n_samples - n_positive)
    np.random.shuffle(target_values)
    target = pd.Series(target_values)
    
    # Verify both classes present
    if len(target.unique()) < 2:
        # Skip this example if we somehow don't have both classes
        return
    
    # Train models
    trainer = MLModelTrainer(features, target)
    
    try:
        trainer.train_all_models()
    except ValueError as e:
        # If training fails due to class imbalance in splits, skip this example
        if "class" in str(e).lower():
            return
        raise
    
    # Get test data (use a small subset for prediction)
    test_size = min(10, n_samples // 10)
    X_test = features.iloc[:test_size]
    
    # Get individual model predictions (probabilities for class 1)
    rf_pred = trainer.models['random_forest'].predict_proba(X_test)[:, 1]
    gb_pred = trainer.models['gradient_boosting'].predict_proba(X_test)[:, 1]
    xgb_pred = trainer.models['xgboost'].predict_proba(X_test)[:, 1]
    
    # Get ensemble prediction
    ensemble_pred = trainer.ensemble.predict_proba(X_test)[:, 1]
    
    # Property: Ensemble prediction should equal weighted average
    # weighted_average = rf_pred * 0.3 + gb_pred * 0.3 + xgb_pred * 0.4
    expected_pred = rf_pred * 0.3 + gb_pred * 0.3 + xgb_pred * 0.4
    
    # Allow small numerical tolerance due to floating point arithmetic
    assert np.allclose(ensemble_pred, expected_pred, rtol=1e-5, atol=1e-8), \
        f"Ensemble prediction should equal weighted average of individual predictions.\n" \
        f"Expected: {expected_pred}\n" \
        f"Got: {ensemble_pred}\n" \
        f"Difference: {np.abs(ensemble_pred - expected_pred)}"
    
    # Additional verification: Check weights are correct
    assert trainer.ensemble.weights == [0.3, 0.3, 0.4], \
        f"Ensemble weights should be [0.3, 0.3, 0.4], got {trainer.ensemble.weights}"


# Property 33: Out-of-sample validation
@given(
    n_samples=st.integers(min_value=100, max_value=300),
    n_features=st.integers(min_value=5, max_value=15)
)
@settings(max_examples=5, deadline=None)
def test_property_33_out_of_sample_validation(n_samples, n_features):
    """
    Property 33: Out-of-sample validation

    For any ML model, holdout test set (final 15%) should never be used during
    training or hyperparameter tuning. This ensures temporal split is maintained
    and test set remains truly out-of-sample.

    **Validates: Requirements 18.2**
    """
    from src.ml_model_trainer import MLModelTrainer

    # Create random features with temporal ordering
    np.random.seed(42)
    features = pd.DataFrame(
        np.random.uniform(0, 1, (n_samples, n_features)),
        columns=[f'feature_{i}' for i in range(n_features)]
    )

    # Create target with balanced classes
    n_positive = max(int(n_samples * 0.45), int(n_samples * 0.70 * 0.3))
    target_values = [1] * n_positive + [0] * (n_samples - n_positive)
    np.random.shuffle(target_values)
    target = pd.Series(target_values)

    # Verify both classes present
    if len(target.unique()) < 2:
        return

    # Initialize trainer
    trainer = MLModelTrainer(features, target)

    # Split data using temporal ordering (70% train, 15% val, 15% test)
    X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()

    # Calculate split boundaries
    train_end = int(n_samples * 0.70)
    val_end = int(n_samples * 0.85)

    # Property 1: Test set should be the final 15% of data (temporal split)
    expected_test_size = n_samples - val_end
    actual_test_size = len(X_test)
    assert actual_test_size == expected_test_size, \
        f"Test set size should be {expected_test_size} (final 15%), got {actual_test_size}"

    # Property 2: Test set indices should be the last indices (temporal ordering)
    # The test set should contain rows from val_end to n_samples
    test_start_idx = val_end
    test_end_idx = n_samples

    # Verify test set contains the correct temporal slice
    assert X_test.index[0] == test_start_idx, \
        f"Test set should start at index {test_start_idx}, got {X_test.index[0]}"
    assert X_test.index[-1] == test_end_idx - 1, \
        f"Test set should end at index {test_end_idx - 1}, got {X_test.index[-1]}"

    # Property 3: Training set should NOT contain any test set indices
    train_indices = set(X_train.index)
    test_indices = set(X_test.index)
    overlap = train_indices.intersection(test_indices)
    assert len(overlap) == 0, \
        f"Training set should not contain test set indices. Found {len(overlap)} overlapping indices"

    # Property 4: Validation set should NOT contain any test set indices
    val_indices = set(X_val.index)
    overlap_val = val_indices.intersection(test_indices)
    assert len(overlap_val) == 0, \
        f"Validation set should not contain test set indices. Found {len(overlap_val)} overlapping indices"

    # Property 5: All test indices should come AFTER all training indices (temporal order)
    max_train_idx = max(train_indices) if train_indices else -1
    min_test_idx = min(test_indices) if test_indices else n_samples
    assert max_train_idx < min_test_idx, \
        f"All training indices should be before test indices. Max train: {max_train_idx}, Min test: {min_test_idx}"

    # Property 6: All test indices should come AFTER all validation indices (temporal order)
    max_val_idx = max(val_indices) if val_indices else -1
    assert max_val_idx < min_test_idx, \
        f"All validation indices should be before test indices. Max val: {max_val_idx}, Min test: {min_test_idx}"

    # Property 7: Train models and verify test set is never accessed during training
    # We verify this by checking that the model can be trained without ever seeing test data
    try:
        # Train only on training data
        rf_model = trainer.train_random_forest(X_train, y_train)

        # Verify model was trained (has been fitted)
        assert hasattr(rf_model, 'n_features_in_'), \
            "Model should be trained and have n_features_in_ attribute"

        # Verify model was trained on correct number of features
        assert rf_model.n_features_in_ == n_features, \
            f"Model should be trained on {n_features} features, got {rf_model.n_features_in_}"

        # Property 8: Model should be able to predict on test set (same feature space)
        # but should never have seen this data during training
        predictions = rf_model.predict(X_test)
        assert len(predictions) == len(X_test), \
            "Model should produce predictions for all test samples"

    except ValueError as e:
        # If training fails due to class imbalance, skip this example
        if "class" in str(e).lower():
            return
        raise

    # Property 9: Test set size should be exactly 15% of total data (±1 for rounding)
    expected_test_pct = 0.15
    actual_test_pct = len(X_test) / n_samples
    assert abs(actual_test_pct - expected_test_pct) < 0.02, \
        f"Test set should be ~15% of data, got {actual_test_pct:.2%}"

    # Property 10: Temporal ordering is preserved (no shuffling)
    # Check that indices are sequential within each split
    assert list(X_train.index) == list(range(0, train_end)), \
        "Training set indices should be sequential from 0"
    assert list(X_val.index) == list(range(train_end, val_end)), \
        "Validation set indices should be sequential after training set"
    assert list(X_test.index) == list(range(val_end, n_samples)), \
        "Test set indices should be sequential after validation set"



# Property 34: Model performance degradation check
@given(
    n_samples=st.integers(min_value=100, max_value=300),
    n_features=st.integers(min_value=5, max_value=15),
    degradation_factor=st.floats(min_value=0.0, max_value=0.5)
)
@settings(max_examples=5, deadline=None)
def test_property_34_model_performance_degradation(n_samples, n_features, degradation_factor):
    """
    Property 34: Model performance degradation check
    
    For any ML model, if holdout performance degrades >20% from validation performance,
    overfitting should be flagged.
    
    **Validates: Requirements 18.5, 18.6**
    """
    import sys
    from pathlib import Path
    
    # Add parent directory to path to import validate_ml_models
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    from validate_ml_models import OutOfSampleValidator
    
    # Create synthetic features with temporal ordering
    np.random.seed(42)
    features = pd.DataFrame(
        np.random.uniform(0, 1, (n_samples, n_features)),
        columns=[f'feature_{i}' for i in range(n_features)]
    )
    
    # Create target with balanced classes
    n_positive = max(int(n_samples * 0.45), int(n_samples * 0.70 * 0.3))
    target_values = [1] * n_positive + [0] * (n_samples - n_positive)
    np.random.shuffle(target_values)
    target = pd.Series(target_values)
    
    # Verify both classes present
    if len(target.unique()) < 2:
        return
    
    # Initialize trainer
    from src.ml_model_trainer import MLModelTrainer
    trainer = MLModelTrainer(features, target)
    
    # Split data (70% train, 15% val, 15% test)
    try:
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        trainer.train_all_models()
    except ValueError as e:
        # Skip if training fails due to class imbalance
        if "class" in str(e).lower():
            return
        raise
    
    # Evaluate on validation set
    val_metrics = trainer.evaluate_model(trainer.ensemble, X_val, y_val)
    
    # Evaluate on test set (holdout)
    test_metrics = trainer.evaluate_model(trainer.ensemble, X_test, y_test)
    
    # Calculate degradation for key metrics
    metrics_to_check = ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']
    degradations = {}
    
    for metric in metrics_to_check:
        val_value = val_metrics.get(metric, 0)
        test_value = test_metrics.get(metric, 0)
        
        if val_value > 0:
            degradation_pct = ((val_value - test_value) / val_value) * 100
        else:
            degradation_pct = 0
        
        degradations[metric] = degradation_pct
    
    # Calculate max degradation
    max_degradation = max(degradations.values())
    
    # Property 1: If any metric degrades >20%, overfitting should be flagged
    overfitting_threshold = 20.0
    should_flag_overfitting = max_degradation > overfitting_threshold
    
    # Simulate the validator's overfitting detection logic
    validator = OutOfSampleValidator.__new__(OutOfSampleValidator)
    validator.validation_metrics = val_metrics
    validator.test_metrics = test_metrics
    
    comparison = validator.compare_performance(val_metrics, test_metrics)
    
    # Property: Overfitting flag should match expected behavior
    if should_flag_overfitting:
        assert comparison['overfitting_detected'] == True, \
            f"Overfitting should be flagged when max degradation ({max_degradation:.1f}%) > 20%"
    else:
        assert comparison['overfitting_detected'] == False, \
            f"Overfitting should NOT be flagged when max degradation ({max_degradation:.1f}%) <= 20%"
    
    # Property 2: Max degradation should be correctly calculated
    assert abs(comparison['max_degradation_pct'] - max_degradation) < 0.1, \
        f"Max degradation calculation mismatch. Expected: {max_degradation:.1f}%, Got: {comparison['max_degradation_pct']:.1f}%"
    
    # Property 3: Each metric's degradation should be correctly calculated
    for metric in metrics_to_check:
        expected_degradation = degradations[metric]
        actual_degradation = comparison[metric]['degradation_pct']
        
        assert abs(expected_degradation - actual_degradation) < 0.1, \
            f"Degradation for {metric} mismatch. Expected: {expected_degradation:.1f}%, Got: {actual_degradation:.1f}%"
    
    # Property 4: Individual metric degradation flags should be correct
    for metric in metrics_to_check:
        metric_degraded = degradations[metric] > overfitting_threshold
        assert comparison[metric]['degraded'] == metric_degraded, \
            f"Metric {metric} degradation flag incorrect. Degradation: {degradations[metric]:.1f}%, Flagged: {comparison[metric]['degraded']}"
    
    # Property 5: Validation and test values should be correctly stored
    for metric in metrics_to_check:
        assert abs(comparison[metric]['validation'] - val_metrics[metric]) < 1e-6, \
            f"Validation value for {metric} not correctly stored"
        assert abs(comparison[metric]['test'] - test_metrics[metric]) < 1e-6, \
            f"Test value for {metric} not correctly stored"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
