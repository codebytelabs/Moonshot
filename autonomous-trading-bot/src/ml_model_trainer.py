"""
ML Model Trainer Module

Trains ensemble of machine learning models (Random Forest, Gradient Boosting, XGBoost)
for improving trade selection accuracy. Implements temporal data splitting, model training
with configured hyperparameters, and weighted ensemble creation.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from xgboost import XGBClassifier
import logging
import joblib
from pathlib import Path

logger = logging.getLogger(__name__)


class MLModelTrainer:
    """
    ML model training module for trade selection improvement.
    
    Trains three model types (Random Forest, Gradient Boosting, XGBoost) with
    configured hyperparameters and creates a weighted ensemble for predictions.
    Maintains temporal order in data splitting to prevent look-ahead bias.
    """
    
    def __init__(self, features: pd.DataFrame, target: pd.Series):
        """
        Initialize ML model trainer.
        
        Args:
            features: DataFrame with normalized features (excluding target)
            target: Series with binary target variable (1 if R-multiple > 1.5, else 0)
        """
        self.features = features
        self.target = target
        self.models = {}
        self.ensemble = None
        
        # Validate inputs
        if len(features) != len(target):
            raise ValueError(f"Features and target length mismatch: {len(features)} vs {len(target)}")
        
        logger.info(f"Initialized MLModelTrainer with {len(features)} samples, {len(features.columns)} features")
    
    def split_data(self, train_pct: float = 0.70, val_pct: float = 0.15) -> Tuple:
        """
        Split data into train, validation, and test sets maintaining temporal order.
        
        Temporal splitting ensures no look-ahead bias by using:
        - First 70% for training
        - Next 15% for validation
        - Final 15% for testing
        
        Args:
            train_pct: Percentage of data for training (default: 0.70)
            val_pct: Percentage of data for validation (default: 0.15)
            
        Returns:
            Tuple of (X_train, X_val, X_test, y_train, y_val, y_test)
        """
        n_samples = len(self.features)
        
        # Calculate split indices
        train_end = int(n_samples * train_pct)
        val_end = int(n_samples * (train_pct + val_pct))
        
        # Split features
        X_train = self.features.iloc[:train_end]
        X_val = self.features.iloc[train_end:val_end]
        X_test = self.features.iloc[val_end:]
        
        # Split target
        y_train = self.target.iloc[:train_end]
        y_val = self.target.iloc[train_end:val_end]
        y_test = self.target.iloc[val_end:]
        
        logger.info(f"Data split - Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
        logger.info(f"Target distribution - Train: {y_train.mean():.3f}, Val: {y_val.mean():.3f}, Test: {y_test.mean():.3f}")
        
        return X_train, X_val, X_test, y_train, y_val, y_test

    
    def train_random_forest(self, X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
        """
        Train Random Forest classifier with configured hyperparameters.
        
        Hyperparameters (from design doc):
        - n_estimators: 200
        - max_depth: 10
        - min_samples_split: 50
        - min_samples_leaf: 20
        - max_features: 'sqrt'
        - bootstrap: True
        
        Args:
            X_train: Training features
            y_train: Training target
            
        Returns:
            Trained RandomForestClassifier
        """
        logger.info("Training Random Forest model...")
        
        rf_params = {
            'n_estimators': 200,
            'max_depth': 10,
            'min_samples_split': 50,
            'min_samples_leaf': 20,
            'max_features': 'sqrt',
            'bootstrap': True,
            'random_state': 42,
            'n_jobs': -1
        }
        
        rf_model = RandomForestClassifier(**rf_params)
        rf_model.fit(X_train, y_train)
        
        logger.info("Random Forest training complete")
        return rf_model
    
    def train_gradient_boosting(self, X_train: pd.DataFrame, y_train: pd.Series) -> GradientBoostingClassifier:
        """
        Train Gradient Boosting classifier with configured hyperparameters.
        
        Hyperparameters (from design doc):
        - n_estimators: 150
        - learning_rate: 0.05
        - max_depth: 8
        - min_samples_split: 50
        - min_samples_leaf: 20
        - subsample: 0.8
        
        Args:
            X_train: Training features
            y_train: Training target
            
        Returns:
            Trained GradientBoostingClassifier
        """
        logger.info("Training Gradient Boosting model...")
        
        gb_params = {
            'n_estimators': 150,
            'learning_rate': 0.05,
            'max_depth': 8,
            'min_samples_split': 50,
            'min_samples_leaf': 20,
            'subsample': 0.8,
            'random_state': 42
        }
        
        gb_model = GradientBoostingClassifier(**gb_params)
        gb_model.fit(X_train, y_train)
        
        logger.info("Gradient Boosting training complete")
        return gb_model
    
    def train_xgboost(self, X_train: pd.DataFrame, y_train: pd.Series) -> XGBClassifier:
        """
        Train XGBoost classifier with configured hyperparameters.
        
        Hyperparameters (from design doc):
        - n_estimators: 200
        - learning_rate: 0.05
        - max_depth: 8
        - min_child_weight: 5
        - subsample: 0.8
        - colsample_bytree: 0.8
        - gamma: 0.1
        
        Args:
            X_train: Training features
            y_train: Training target
            
        Returns:
            Trained XGBClassifier
        """
        logger.info("Training XGBoost model...")
        
        xgb_params = {
            'n_estimators': 200,
            'learning_rate': 0.05,
            'max_depth': 8,
            'min_child_weight': 5,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'gamma': 0.1,
            'random_state': 42,
            'n_jobs': -1,
            'eval_metric': 'logloss'
        }
        
        xgb_model = XGBClassifier(**xgb_params)
        xgb_model.fit(X_train, y_train)
        
        logger.info("XGBoost training complete")
        return xgb_model

    
    def create_ensemble(self, models: List, weights: List[float]) -> VotingClassifier:
        """
        Create weighted ensemble from trained models.
        
        Ensemble weights (from design doc):
        - Random Forest: 0.3
        - Gradient Boosting: 0.3
        - XGBoost: 0.4
        
        Args:
            models: List of trained models [rf, gb, xgb]
            weights: List of weights [0.3, 0.3, 0.4]
            
        Returns:
            VotingClassifier ensemble
        """
        logger.info("Creating weighted ensemble...")
        
        if len(models) != 3:
            raise ValueError(f"Expected 3 models, got {len(models)}")
        
        if len(weights) != 3:
            raise ValueError(f"Expected 3 weights, got {len(weights)}")
        
        if not np.isclose(sum(weights), 1.0):
            raise ValueError(f"Weights must sum to 1.0, got {sum(weights)}")
        
        # Create ensemble with soft voting (uses predicted probabilities)
        ensemble = VotingClassifier(
            estimators=[
                ('rf', models[0]),
                ('gb', models[1]),
                ('xgb', models[2])
            ],
            voting='soft',
            weights=weights
        )
        
        logger.info(f"Ensemble created with weights: RF={weights[0]}, GB={weights[1]}, XGB={weights[2]}")
        return ensemble
    
    def evaluate_model(self, model, X_test: pd.DataFrame, y_test: pd.Series) -> Dict:
        """
        Evaluate model performance on test set.
        
        Calculates:
        - Accuracy: Overall correctness
        - Precision: True positives / (True positives + False positives)
        - Recall: True positives / (True positives + False negatives)
        - F1-score: Harmonic mean of precision and recall
        - ROC-AUC: Area under ROC curve
        
        Args:
            model: Trained model to evaluate
            X_test: Test features
            y_test: Test target
            
        Returns:
            Dict with evaluation metrics
        """
        logger.info("Evaluating model performance...")
        
        # Get predictions
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        
        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1_score': f1_score(y_test, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_test, y_pred_proba)
        }
        
        logger.info(f"Evaluation metrics: {metrics}")
        return metrics
    
    def train_all_models(self) -> Dict:
        """
        Train all models and create ensemble.
        
        Complete training pipeline:
        1. Split data (70% train, 15% val, 15% test)
        2. Train Random Forest
        3. Train Gradient Boosting
        4. Train XGBoost
        5. Create weighted ensemble (RF=0.3, GB=0.3, XGB=0.4)
        6. Evaluate on validation set
        
        Returns:
            Dict with trained models and evaluation metrics
        """
        logger.info("Starting complete model training pipeline...")
        
        # Split data
        X_train, X_val, X_test, y_train, y_val, y_test = self.split_data()
        
        # Train individual models
        rf_model = self.train_random_forest(X_train, y_train)
        gb_model = self.train_gradient_boosting(X_train, y_train)
        xgb_model = self.train_xgboost(X_train, y_train)
        
        # Store models
        self.models = {
            'random_forest': rf_model,
            'gradient_boosting': gb_model,
            'xgboost': xgb_model
        }
        
        # Create ensemble
        ensemble_weights = [0.3, 0.3, 0.4]
        self.ensemble = self.create_ensemble(
            [rf_model, gb_model, xgb_model],
            ensemble_weights
        )
        
        # Fit ensemble (required for VotingClassifier even though base models are trained)
        logger.info("Fitting ensemble...")
        self.ensemble.fit(X_train, y_train)
        
        # Evaluate individual models on validation set
        logger.info("Evaluating individual models on validation set...")
        rf_metrics = self.evaluate_model(rf_model, X_val, y_val)
        gb_metrics = self.evaluate_model(gb_model, X_val, y_val)
        xgb_metrics = self.evaluate_model(xgb_model, X_val, y_val)
        
        # Evaluate ensemble on validation set
        logger.info("Evaluating ensemble on validation set...")
        ensemble_metrics = self.evaluate_model(self.ensemble, X_val, y_val)
        
        # Store test sets for later evaluation
        self.X_test = X_test
        self.y_test = y_test
        
        results = {
            'models': self.models,
            'ensemble': self.ensemble,
            'validation_metrics': {
                'random_forest': rf_metrics,
                'gradient_boosting': gb_metrics,
                'xgboost': xgb_metrics,
                'ensemble': ensemble_metrics
            },
            'data_splits': {
                'train_size': len(X_train),
                'val_size': len(X_val),
                'test_size': len(X_test)
            }
        }
        
        logger.info("Model training pipeline complete")
        logger.info(f"Ensemble validation accuracy: {ensemble_metrics['accuracy']:.4f}")
        
        return results

    
    def save_models(self, output_dir: str = "ml_models") -> None:
        """
        Save trained models to disk.
        
        Args:
            output_dir: Directory to save models (default: "ml_models")
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save individual models
        for model_name, model in self.models.items():
            model_file = output_path / f"{model_name}.joblib"
            joblib.dump(model, model_file)
            logger.info(f"Saved {model_name} to {model_file}")
        
        # Save ensemble
        if self.ensemble is not None:
            ensemble_file = output_path / "ensemble.joblib"
            joblib.dump(self.ensemble, ensemble_file)
            logger.info(f"Saved ensemble to {ensemble_file}")
    
    def load_models(self, input_dir: str = "ml_models") -> None:
        """
        Load trained models from disk.
        
        Args:
            input_dir: Directory containing saved models (default: "ml_models")
        """
        input_path = Path(input_dir)
        
        # Load individual models
        model_names = ['random_forest', 'gradient_boosting', 'xgboost']
        for model_name in model_names:
            model_file = input_path / f"{model_name}.joblib"
            if model_file.exists():
                self.models[model_name] = joblib.load(model_file)
                logger.info(f"Loaded {model_name} from {model_file}")
        
        # Load ensemble
        ensemble_file = input_path / "ensemble.joblib"
        if ensemble_file.exists():
            self.ensemble = joblib.load(ensemble_file)
            logger.info(f"Loaded ensemble from {ensemble_file}")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make predictions using the ensemble model.
        
        Args:
            X: Features to predict on
            
        Returns:
            Array of predictions (0 or 1)
        """
        if self.ensemble is None:
            raise ValueError("Ensemble not trained. Call train_all_models() first.")
        
        return self.ensemble.predict(X)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get prediction probabilities using the ensemble model.
        
        Args:
            X: Features to predict on
            
        Returns:
            Array of probabilities for each class
        """
        if self.ensemble is None:
            raise ValueError("Ensemble not trained. Call train_all_models() first.")
        
        return self.ensemble.predict_proba(X)
