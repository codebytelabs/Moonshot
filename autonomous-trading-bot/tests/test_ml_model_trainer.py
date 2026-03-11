"""
Unit tests for ML Model Trainer module.

Tests the ML model training pipeline including data splitting, individual model training,
ensemble creation, and evaluation.
"""

import pytest
import pandas as pd
import numpy as np
from src.ml_model_trainer import MLModelTrainer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from xgboost import XGBClassifier


@pytest.fixture
def sample_features():
    """Create sample feature matrix."""
    np.random.seed(42)
    n_samples = 1000
    
    features = pd.DataFrame({
        'ta_score': np.random.uniform(0, 1, n_samples),
        'volume_spike': np.random.uniform(0, 1, n_samples),
        'sentiment_score': np.random.uniform(0, 1, n_samples),
        'volatility_percentile': np.random.uniform(0, 1, n_samples),
        'trend_strength': np.random.uniform(0, 1, n_samples),
        'score_momentum': np.random.uniform(0, 1, n_samples),
        'volume_acceleration': np.random.uniform(0, 1, n_samples),
        'sentiment_shift': np.random.uniform(0, 1, n_samples),
        'bull_market': np.random.randint(0, 2, n_samples),
        'bear_market': np.random.randint(0, 2, n_samples),
        'high_volatility': np.random.randint(0, 2, n_samples),
        'low_volatility': np.random.randint(0, 2, n_samples),
        'hour_of_day': np.random.uniform(0, 1, n_samples),
        'day_of_week': np.random.uniform(0, 1, n_samples),
        'days_since_last_trade': np.random.uniform(0, 1, n_samples)
    })
    
    return features


@pytest.fixture
def sample_target():
    """Create sample target variable."""
    np.random.seed(42)
    n_samples = 1000
    # Create target with ~55% positive class
    target = pd.Series(np.random.choice([0, 1], n_samples, p=[0.45, 0.55]))
    return target


@pytest.fixture
def trainer(sample_features, sample_target):
    """Create MLModelTrainer instance."""
    return MLModelTrainer(sample_features, sample_target)


class TestMLModelTrainerInit:
    """Test MLModelTrainer initialization."""
    
    def test_init_success(self, sample_features, sample_target):
        """Test successful initialization."""
        trainer = MLModelTrainer(sample_features, sample_target)
        
        assert len(trainer.features) == len(sample_features)
        assert len(trainer.target) == len(sample_target)
        assert trainer.models == {}
        assert trainer.ensemble is None
    
    def test_init_length_mismatch(self, sample_features, sample_target):
        """Test initialization fails with mismatched lengths."""
        short_target = sample_target[:500]
        
        with pytest.raises(ValueError, match="Features and target length mismatch"):
            MLModelTrainer(sample_features, short_target)


class TestDataSplitting:
    """Test data splitting functionality."""
    
    def test_split_data_default(self, trainer):
        """Test data splitting with default percentages."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        # Check sizes
        total = len(trainer.features)
        assert len(X_train) == int(total * 0.70)
        assert len(X_val) == int(total * 0.15)
        assert len(X_test) == total - len(X_train) - len(X_val)
        
        # Check target sizes match
        assert len(y_train) == len(X_train)
        assert len(y_val) == len(X_val)
        assert len(y_test) == len(X_test)
    
    def test_split_data_custom(self, trainer):
        """Test data splitting with custom percentages."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data(
            train_pct=0.60, val_pct=0.20
        )
        
        total = len(trainer.features)
        assert len(X_train) == int(total * 0.60)
        assert len(X_val) == int(total * 0.20)
        assert len(X_test) == total - len(X_train) - len(X_val)
    
    def test_split_maintains_temporal_order(self, trainer):
        """Test that splitting maintains temporal order."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        # Check indices are sequential
        assert X_train.index[-1] < X_val.index[0]
        assert X_val.index[-1] < X_test.index[0]


class TestModelTraining:
    """Test individual model training."""
    
    def test_train_random_forest(self, trainer):
        """Test Random Forest training."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        rf_model = trainer.train_random_forest(X_train, y_train)
        
        assert isinstance(rf_model, RandomForestClassifier)
        assert rf_model.n_estimators == 200
        assert rf_model.max_depth == 10
        assert rf_model.min_samples_split == 50
        
        # Test prediction works
        predictions = rf_model.predict(X_val)
        assert len(predictions) == len(X_val)
        assert all(p in [0, 1] for p in predictions)
    
    def test_train_gradient_boosting(self, trainer):
        """Test Gradient Boosting training."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        gb_model = trainer.train_gradient_boosting(X_train, y_train)
        
        assert isinstance(gb_model, GradientBoostingClassifier)
        assert gb_model.n_estimators == 150
        assert gb_model.learning_rate == 0.05
        assert gb_model.max_depth == 8
        
        # Test prediction works
        predictions = gb_model.predict(X_val)
        assert len(predictions) == len(X_val)
        assert all(p in [0, 1] for p in predictions)
    
    def test_train_xgboost(self, trainer):
        """Test XGBoost training."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        xgb_model = trainer.train_xgboost(X_train, y_train)
        
        assert isinstance(xgb_model, XGBClassifier)
        assert xgb_model.n_estimators == 200
        assert xgb_model.learning_rate == 0.05
        assert xgb_model.max_depth == 8
        
        # Test prediction works
        predictions = xgb_model.predict(X_val)
        assert len(predictions) == len(X_val)
        assert all(p in [0, 1] for p in predictions)


class TestEnsembleCreation:
    """Test ensemble creation."""
    
    def test_create_ensemble_success(self, trainer):
        """Test successful ensemble creation."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        # Train models
        rf_model = trainer.train_random_forest(X_train, y_train)
        gb_model = trainer.train_gradient_boosting(X_train, y_train)
        xgb_model = trainer.train_xgboost(X_train, y_train)
        
        # Create ensemble
        ensemble = trainer.create_ensemble(
            [rf_model, gb_model, xgb_model],
            [0.3, 0.3, 0.4]
        )
        
        assert isinstance(ensemble, VotingClassifier)
        assert len(ensemble.estimators) == 3
        assert ensemble.voting == 'soft'
        assert list(ensemble.weights) == [0.3, 0.3, 0.4]
    
    def test_create_ensemble_wrong_model_count(self, trainer):
        """Test ensemble creation fails with wrong number of models."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        rf_model = trainer.train_random_forest(X_train, y_train)
        
        with pytest.raises(ValueError, match="Expected 3 models"):
            trainer.create_ensemble([rf_model], [1.0])
    
    def test_create_ensemble_wrong_weight_count(self, trainer):
        """Test ensemble creation fails with wrong number of weights."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        rf_model = trainer.train_random_forest(X_train, y_train)
        gb_model = trainer.train_gradient_boosting(X_train, y_train)
        xgb_model = trainer.train_xgboost(X_train, y_train)
        
        with pytest.raises(ValueError, match="Expected 3 weights"):
            trainer.create_ensemble([rf_model, gb_model, xgb_model], [0.5, 0.5])
    
    def test_create_ensemble_weights_not_sum_to_one(self, trainer):
        """Test ensemble creation fails when weights don't sum to 1.0."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        rf_model = trainer.train_random_forest(X_train, y_train)
        gb_model = trainer.train_gradient_boosting(X_train, y_train)
        xgb_model = trainer.train_xgboost(X_train, y_train)
        
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            trainer.create_ensemble([rf_model, gb_model, xgb_model], [0.3, 0.3, 0.3])


class TestModelEvaluation:
    """Test model evaluation."""
    
    def test_evaluate_model(self, trainer):
        """Test model evaluation returns all metrics."""
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data()
        
        rf_model = trainer.train_random_forest(X_train, y_train)
        metrics = trainer.evaluate_model(rf_model, X_val, y_val)
        
        # Check all metrics present
        assert 'accuracy' in metrics
        assert 'precision' in metrics
        assert 'recall' in metrics
        assert 'f1_score' in metrics
        assert 'roc_auc' in metrics
        
        # Check metrics are in valid range
        assert 0 <= metrics['accuracy'] <= 1
        assert 0 <= metrics['precision'] <= 1
        assert 0 <= metrics['recall'] <= 1
        assert 0 <= metrics['f1_score'] <= 1
        assert 0 <= metrics['roc_auc'] <= 1


class TestCompleteTrainingPipeline:
    """Test complete training pipeline."""
    
    def test_train_all_models(self, trainer):
        """Test complete training pipeline."""
        results = trainer.train_all_models()
        
        # Check models trained
        assert 'random_forest' in results['models']
        assert 'gradient_boosting' in results['models']
        assert 'xgboost' in results['models']
        
        # Check ensemble created
        assert results['ensemble'] is not None
        assert isinstance(results['ensemble'], VotingClassifier)
        
        # Check validation metrics
        assert 'random_forest' in results['validation_metrics']
        assert 'gradient_boosting' in results['validation_metrics']
        assert 'xgboost' in results['validation_metrics']
        assert 'ensemble' in results['validation_metrics']
        
        # Check data splits
        assert results['data_splits']['train_size'] == 700
        assert results['data_splits']['val_size'] == 150
        assert results['data_splits']['test_size'] == 150
        
        # Check ensemble accuracy is reasonable
        ensemble_accuracy = results['validation_metrics']['ensemble']['accuracy']
        assert 0.4 <= ensemble_accuracy <= 1.0  # Should be better than random
    
    def test_predict_after_training(self, trainer):
        """Test prediction works after training."""
        trainer.train_all_models()
        
        # Create test data
        test_features = trainer.features.iloc[:10]
        
        # Test predict
        predictions = trainer.predict(test_features)
        assert len(predictions) == 10
        assert all(p in [0, 1] for p in predictions)
        
        # Test predict_proba
        probas = trainer.predict_proba(test_features)
        assert probas.shape == (10, 2)
        assert np.allclose(probas.sum(axis=1), 1.0)
    
    def test_predict_before_training_fails(self, trainer):
        """Test prediction fails before training."""
        test_features = trainer.features.iloc[:10]
        
        with pytest.raises(ValueError, match="Ensemble not trained"):
            trainer.predict(test_features)
        
        with pytest.raises(ValueError, match="Ensemble not trained"):
            trainer.predict_proba(test_features)


class TestModelPersistence:
    """Test model saving and loading."""
    
    def test_save_and_load_models(self, trainer, tmp_path):
        """Test saving and loading models."""
        # Train models
        trainer.train_all_models()
        
        # Save models
        output_dir = str(tmp_path / "test_models")
        trainer.save_models(output_dir)
        
        # Create new trainer and load models
        new_trainer = MLModelTrainer(trainer.features, trainer.target)
        new_trainer.load_models(output_dir)
        
        # Check models loaded
        assert 'random_forest' in new_trainer.models
        assert 'gradient_boosting' in new_trainer.models
        assert 'xgboost' in new_trainer.models
        assert new_trainer.ensemble is not None
        
        # Test predictions match
        test_features = trainer.features.iloc[:10]
        original_pred = trainer.predict(test_features)
        loaded_pred = new_trainer.predict(test_features)
        
        assert np.array_equal(original_pred, loaded_pred)
