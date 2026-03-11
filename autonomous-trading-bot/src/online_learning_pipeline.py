"""
Online Learning Pipeline Module

Enables continuous model improvement from new trade outcomes without full retraining.
Accumulates trade outcomes, triggers incremental updates, validates performance,
and rolls back if degradation occurs.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import logging
import joblib
from collections import deque
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)


class OnlineLearningPipeline:
    """
    Online learning pipeline for continuous model improvement.
    
    Accumulates new trade outcomes and performs incremental model updates
    when threshold is reached. Validates updated models and rolls back
    if performance degrades beyond acceptable limits.
    """
    
    def __init__(self, 
                 base_models: Dict,
                 update_threshold: int = 50,
                 rolling_window: int = 1000,
                 validation_window: int = 100,
                 degradation_threshold: float = 0.10,
                 retrain_interval_days: int = 90):
        """
        Initialize online learning pipeline.
        
        Args:
            base_models: Dict with trained models {'random_forest': model, 'gradient_boosting': model, 'xgboost': model, 'ensemble': model}
            update_threshold: Number of new outcomes to trigger update (default: 50)
            rolling_window: Size of rolling window for training (default: 1000)
            validation_window: Number of recent trades for validation (default: 100)
            degradation_threshold: Max acceptable performance degradation (default: 0.10 = 10%)
            retrain_interval_days: Days between full retraining (default: 90 = 3 months)
        """
        self.base_models = base_models
        self.current_models = {k: v for k, v in base_models.items()}  # Copy for current version
        self.previous_models = None  # For rollback
        
        self.update_threshold = update_threshold
        self.rolling_window = rolling_window
        self.validation_window = validation_window
        self.degradation_threshold = degradation_threshold
        self.retrain_interval_days = retrain_interval_days
        
        # Accumulation buffer for new trade outcomes
        self.outcome_buffer = deque(maxlen=rolling_window)
        self.new_outcomes_count = 0
        
        # Model versioning
        self.model_version = 1
        self.last_update_time = datetime.now()
        self.last_full_retrain = datetime.now()
        
        # Performance tracking
        self.performance_history = []
        
        logger.info(f"Initialized OnlineLearningPipeline - update_threshold={update_threshold}, "
                   f"rolling_window={rolling_window}, validation_window={validation_window}")
    
    def accumulate_trade_outcome(self, features: Dict, outcome: bool) -> None:
        """
        Add new trade outcome to accumulation buffer.
        
        Args:
            features: Dict of feature values for the trade
            outcome: Boolean indicating trade success (True if R-multiple > 1.5, False otherwise)
        """
        trade_data = {
            'features': features,
            'outcome': outcome,
            'timestamp': datetime.now()
        }
        
        self.outcome_buffer.append(trade_data)
        self.new_outcomes_count += 1
        
        logger.debug(f"Accumulated trade outcome: success={outcome}, buffer_size={len(self.outcome_buffer)}, "
                    f"new_count={self.new_outcomes_count}")
    
    def should_update(self) -> bool:
        """
        Check if update threshold has been reached.
        
        Returns:
            True if incremental update should be triggered
        """
        should_trigger = self.new_outcomes_count >= self.update_threshold
        
        if should_trigger:
            logger.info(f"Update threshold reached: {self.new_outcomes_count} >= {self.update_threshold}")
        
        return should_trigger
    
    def should_full_retrain(self) -> bool:
        """
        Check if full retraining should be scheduled.
        
        Returns:
            True if 3 months have passed since last full retrain
        """
        days_since_retrain = (datetime.now() - self.last_full_retrain).days
        should_retrain = days_since_retrain >= self.retrain_interval_days
        
        if should_retrain:
            logger.info(f"Full retrain scheduled: {days_since_retrain} days since last retrain")
        
        return should_retrain
    
    def _prepare_training_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from outcome buffer.
        
        Returns:
            Tuple of (features_df, target_series)
        """
        if len(self.outcome_buffer) == 0:
            raise ValueError("Outcome buffer is empty")
        
        # Extract features and outcomes
        features_list = []
        outcomes_list = []
        
        for trade_data in self.outcome_buffer:
            features_list.append(trade_data['features'])
            outcomes_list.append(int(trade_data['outcome']))
        
        # Convert to DataFrame and Series
        features_df = pd.DataFrame(features_list)
        target_series = pd.Series(outcomes_list)
        
        logger.info(f"Prepared training data: {len(features_df)} samples, "
                   f"positive_rate={target_series.mean():.3f}")
        
        return features_df, target_series
    
    def _prepare_validation_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare validation data from recent trades in buffer.
        
        Returns:
            Tuple of (features_df, target_series) for last validation_window trades
        """
        if len(self.outcome_buffer) < self.validation_window:
            logger.warning(f"Buffer size {len(self.outcome_buffer)} < validation_window {self.validation_window}, "
                          f"using all available data")
            validation_size = len(self.outcome_buffer)
        else:
            validation_size = self.validation_window
        
        # Get recent trades
        recent_trades = list(self.outcome_buffer)[-validation_size:]
        
        features_list = []
        outcomes_list = []
        
        for trade_data in recent_trades:
            features_list.append(trade_data['features'])
            outcomes_list.append(int(trade_data['outcome']))
        
        features_df = pd.DataFrame(features_list)
        target_series = pd.Series(outcomes_list)
        
        logger.info(f"Prepared validation data: {len(features_df)} samples")
        
        return features_df, target_series
    
    async def incremental_update(self) -> Dict:
        """
        Perform incremental model update using rolling window.
        
        For tree-based models (RF, GB, XGB), retrains on rolling window.
        Updates ensemble with new base models.
        
        Returns:
            Dict with update results and metrics
        """
        logger.info(f"Starting incremental update (version {self.model_version} -> {self.model_version + 1})...")
        
        try:
            # Prepare training data from rolling window
            X_train, y_train = self._prepare_training_data()
            
            # Store previous models for potential rollback
            self.previous_models = {k: v for k, v in self.current_models.items()}
            
            # Retrain individual models on rolling window
            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
            from xgboost import XGBClassifier
            
            # Random Forest
            logger.info("Retraining Random Forest on rolling window...")
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
            
            # Gradient Boosting
            logger.info("Retraining Gradient Boosting on rolling window...")
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
            
            # XGBoost
            logger.info("Retraining XGBoost on rolling window...")
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
            
            # Create new ensemble
            from sklearn.ensemble import VotingClassifier
            
            logger.info("Creating updated ensemble...")
            ensemble_weights = [0.3, 0.3, 0.4]
            ensemble = VotingClassifier(
                estimators=[
                    ('rf', rf_model),
                    ('gb', gb_model),
                    ('xgb', xgb_model)
                ],
                voting='soft',
                weights=ensemble_weights
            )
            ensemble.fit(X_train, y_train)
            
            # Update current models
            updated_models = {
                'random_forest': rf_model,
                'gradient_boosting': gb_model,
                'xgboost': xgb_model,
                'ensemble': ensemble
            }
            
            # Validate updated models
            validation_passed = self.validate_updated_model(updated_models)
            
            if validation_passed:
                # Deploy updated models
                self.current_models = updated_models
                self.model_version += 1
                self.last_update_time = datetime.now()
                self.new_outcomes_count = 0  # Reset counter
                
                logger.info(f"Incremental update successful - deployed version {self.model_version}")
                
                return {
                    'success': True,
                    'model_version': self.model_version,
                    'update_time': self.last_update_time,
                    'training_samples': len(X_train),
                    'validation_passed': True
                }
            else:
                # Rollback to previous models
                logger.warning("Validation failed - rolling back to previous model version")
                self.rollback_model()
                
                return {
                    'success': False,
                    'model_version': self.model_version,
                    'update_time': self.last_update_time,
                    'training_samples': len(X_train),
                    'validation_passed': False,
                    'reason': 'Performance degradation exceeded threshold'
                }
        
        except Exception as e:
            logger.error(f"Incremental update failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_updated_model(self, new_models: Dict) -> bool:
        """
        Validate updated model performance on recent trades.
        
        Compares new model accuracy to previous model on last validation_window trades.
        Requires performance degradation to be less than degradation_threshold (10%).
        
        Args:
            new_models: Dict with updated models to validate
            
        Returns:
            True if validation passes (degradation < 10%), False otherwise
        """
        logger.info("Validating updated model on recent trades...")
        
        try:
            # Prepare validation data
            X_val, y_val = self._prepare_validation_data()
            
            # Get predictions from previous model
            prev_ensemble = self.current_models['ensemble']
            prev_predictions = prev_ensemble.predict(X_val)
            prev_accuracy = accuracy_score(y_val, prev_predictions)
            
            # Get predictions from new model
            new_ensemble = new_models['ensemble']
            new_predictions = new_ensemble.predict(X_val)
            new_accuracy = accuracy_score(y_val, new_predictions)
            
            # Calculate performance change
            if prev_accuracy > 0:
                performance_change = (new_accuracy - prev_accuracy) / prev_accuracy
            else:
                performance_change = 0.0
            
            degradation = -performance_change if performance_change < 0 else 0.0
            
            # Calculate additional metrics
            new_precision = precision_score(y_val, new_predictions, zero_division=0)
            new_recall = recall_score(y_val, new_predictions, zero_division=0)
            new_f1 = f1_score(y_val, new_predictions, zero_division=0)
            
            # Log validation results
            logger.info(f"Validation results:")
            logger.info(f"  Previous accuracy: {prev_accuracy:.4f}")
            logger.info(f"  New accuracy: {new_accuracy:.4f}")
            logger.info(f"  Performance change: {performance_change:+.2%}")
            logger.info(f"  Degradation: {degradation:.2%}")
            logger.info(f"  New precision: {new_precision:.4f}")
            logger.info(f"  New recall: {new_recall:.4f}")
            logger.info(f"  New F1: {new_f1:.4f}")
            
            # Store performance metrics
            self.performance_history.append({
                'timestamp': datetime.now(),
                'model_version': self.model_version + 1,
                'prev_accuracy': prev_accuracy,
                'new_accuracy': new_accuracy,
                'performance_change': performance_change,
                'degradation': degradation,
                'precision': new_precision,
                'recall': new_recall,
                'f1_score': new_f1,
                'validation_samples': len(X_val)
            })
            
            # Check if degradation is acceptable
            validation_passed = degradation <= self.degradation_threshold
            
            if validation_passed:
                logger.info(f"✓ Validation PASSED - degradation {degradation:.2%} <= threshold {self.degradation_threshold:.2%}")
            else:
                logger.warning(f"✗ Validation FAILED - degradation {degradation:.2%} > threshold {self.degradation_threshold:.2%}")
            
            return validation_passed
        
        except Exception as e:
            logger.error(f"Validation failed with error: {e}", exc_info=True)
            return False
    
    def rollback_model(self) -> None:
        """
        Revert to previous model version.
        
        Restores models from previous_models backup.
        """
        if self.previous_models is None:
            logger.warning("No previous models available for rollback")
            return
        
        logger.info(f"Rolling back from version {self.model_version + 1} to version {self.model_version}")
        
        # Restore previous models
        self.current_models = self.previous_models
        self.previous_models = None
        
        logger.info(f"Rollback complete - restored version {self.model_version}")
    
    def schedule_full_retrain(self) -> Dict:
        """
        Schedule complete model retraining.
        
        Returns information about when full retraining should occur.
        This is a scheduling function - actual retraining should be done
        by the main ML training pipeline with complete historical dataset.
        
        Returns:
            Dict with scheduling information
        """
        days_since_retrain = (datetime.now() - self.last_full_retrain).days
        days_until_retrain = max(0, self.retrain_interval_days - days_since_retrain)
        next_retrain_date = self.last_full_retrain + timedelta(days=self.retrain_interval_days)
        
        schedule_info = {
            'last_full_retrain': self.last_full_retrain,
            'days_since_retrain': days_since_retrain,
            'days_until_retrain': days_until_retrain,
            'next_retrain_date': next_retrain_date,
            'retrain_interval_days': self.retrain_interval_days,
            'should_retrain_now': self.should_full_retrain()
        }
        
        logger.info(f"Full retrain schedule: last={self.last_full_retrain.date()}, "
                   f"next={next_retrain_date.date()}, days_until={days_until_retrain}")
        
        return schedule_info
    
    def mark_full_retrain_complete(self, new_models: Dict) -> None:
        """
        Mark full retraining as complete and update models.
        
        Args:
            new_models: Dict with newly trained models from full retraining
        """
        logger.info("Marking full retrain as complete and updating models...")
        
        self.base_models = new_models
        self.current_models = {k: v for k, v in new_models.items()}
        self.previous_models = None
        
        self.last_full_retrain = datetime.now()
        self.model_version += 1
        
        logger.info(f"Full retrain complete - updated to version {self.model_version}")
    
    def get_current_models(self) -> Dict:
        """
        Get current active models.
        
        Returns:
            Dict with current models
        """
        return self.current_models
    
    def get_status(self) -> Dict:
        """
        Get current pipeline status.
        
        Returns:
            Dict with pipeline status information
        """
        return {
            'model_version': self.model_version,
            'last_update_time': self.last_update_time,
            'last_full_retrain': self.last_full_retrain,
            'buffer_size': len(self.outcome_buffer),
            'new_outcomes_count': self.new_outcomes_count,
            'update_threshold': self.update_threshold,
            'should_update': self.should_update(),
            'should_full_retrain': self.should_full_retrain(),
            'performance_history_length': len(self.performance_history)
        }
    
    def save_pipeline_state(self, output_dir: str = "ml_models") -> None:
        """
        Save pipeline state including models and metadata.
        
        Args:
            output_dir: Directory to save pipeline state
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save current models
        for model_name, model in self.current_models.items():
            model_file = output_path / f"online_{model_name}_v{self.model_version}.joblib"
            joblib.dump(model, model_file)
            logger.info(f"Saved {model_name} to {model_file}")
        
        # Save pipeline metadata
        metadata = {
            'model_version': self.model_version,
            'last_update_time': self.last_update_time,
            'last_full_retrain': self.last_full_retrain,
            'update_threshold': self.update_threshold,
            'rolling_window': self.rolling_window,
            'validation_window': self.validation_window,
            'degradation_threshold': self.degradation_threshold,
            'retrain_interval_days': self.retrain_interval_days,
            'performance_history': self.performance_history
        }
        
        metadata_file = output_path / f"online_pipeline_metadata_v{self.model_version}.joblib"
        joblib.dump(metadata, metadata_file)
        logger.info(f"Saved pipeline metadata to {metadata_file}")
    
    def load_pipeline_state(self, input_dir: str = "ml_models", version: Optional[int] = None) -> None:
        """
        Load pipeline state from disk.
        
        Args:
            input_dir: Directory containing saved pipeline state
            version: Specific version to load (default: latest)
        """
        input_path = Path(input_dir)
        
        # Determine version to load
        if version is None:
            # Find latest version
            metadata_files = list(input_path.glob("online_pipeline_metadata_v*.joblib"))
            if not metadata_files:
                raise FileNotFoundError(f"No pipeline metadata found in {input_dir}")
            
            versions = [int(f.stem.split('_v')[-1]) for f in metadata_files]
            version = max(versions)
        
        logger.info(f"Loading pipeline state version {version}...")
        
        # Load models
        model_names = ['random_forest', 'gradient_boosting', 'xgboost', 'ensemble']
        for model_name in model_names:
            model_file = input_path / f"online_{model_name}_v{version}.joblib"
            if model_file.exists():
                self.current_models[model_name] = joblib.load(model_file)
                logger.info(f"Loaded {model_name} from {model_file}")
        
        # Load metadata
        metadata_file = input_path / f"online_pipeline_metadata_v{version}.joblib"
        if metadata_file.exists():
            metadata = joblib.load(metadata_file)
            
            self.model_version = metadata['model_version']
            self.last_update_time = metadata['last_update_time']
            self.last_full_retrain = metadata['last_full_retrain']
            self.update_threshold = metadata['update_threshold']
            self.rolling_window = metadata['rolling_window']
            self.validation_window = metadata['validation_window']
            self.degradation_threshold = metadata['degradation_threshold']
            self.retrain_interval_days = metadata['retrain_interval_days']
            self.performance_history = metadata['performance_history']
            
            logger.info(f"Loaded pipeline metadata from {metadata_file}")
        
        logger.info(f"Pipeline state loaded successfully - version {self.model_version}")
