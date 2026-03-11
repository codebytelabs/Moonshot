#!/usr/bin/env python3
"""
Out-of-Sample Validation Script

Validates trained ML ensemble models on holdout test set to ensure generalization
to unseen market conditions. Calculates comprehensive metrics, compares to validation
performance, flags overfitting, and generates feature importance report.

Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import json
from datetime import datetime
from typing import Dict, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, classification_report
)

from src.ml_model_trainer import MLModelTrainer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OutOfSampleValidator:
    """
    Out-of-sample validation for ML models.
    
    Validates ensemble model on holdout test set, compares to validation performance,
    detects overfitting, and generates comprehensive reports.
    """
    
    def __init__(self, feature_file: str, model_dir: str = "ml_models"):
        """
        Initialize validator.
        
        Args:
            feature_file: Path to feature data file (CSV or Parquet)
            model_dir: Directory containing trained models
        """
        self.feature_file = feature_file
        self.model_dir = model_dir
        self.trainer = None
        self.validation_metrics = None
        self.test_metrics = None
        
    def load_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Load feature data and target variable.
        
        Returns:
            Tuple of (features, target)
        """
        logger.info(f"Loading feature data from {self.feature_file}")
        
        # Load based on file extension
        if self.feature_file.endswith('.parquet'):
            df = pd.read_parquet(self.feature_file)
        elif self.feature_file.endswith('.csv'):
            df = pd.read_csv(self.feature_file)
        else:
            raise ValueError(f"Unsupported file format: {self.feature_file}")
        
        logger.info(f"Loaded {len(df)} samples with {len(df.columns)} columns")
        
        # Separate features and target
        if 'target' not in df.columns:
            raise ValueError("Target column not found in feature data")
        
        target = df['target']
        features = df.drop(columns=['target'])
        
        # Drop any non-numeric columns (like timestamps, symbols)
        non_numeric_cols = features.select_dtypes(exclude=[np.number]).columns
        if len(non_numeric_cols) > 0:
            logger.info(f"Dropping non-numeric columns: {list(non_numeric_cols)}")
            features = features.select_dtypes(include=[np.number])
        
        logger.info(f"Features shape: {features.shape}, Target shape: {target.shape}")
        logger.info(f"Target distribution: {target.value_counts().to_dict()}")
        
        return features, target
    
    def load_models(self) -> None:
        """Load trained models from disk."""
        logger.info(f"Loading models from {self.model_dir}")
        
        # Initialize trainer with dummy data (will be replaced)
        dummy_features = pd.DataFrame([[0]], columns=['dummy'])
        dummy_target = pd.Series([0])
        self.trainer = MLModelTrainer(dummy_features, dummy_target)
        
        # Load actual models
        self.trainer.load_models(self.model_dir)
        
        if self.trainer.ensemble is None:
            raise ValueError("Failed to load ensemble model")
        
        logger.info("Models loaded successfully")
    
    def evaluate_on_test_set(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict:
        """
        Evaluate ensemble on holdout test set.
        
        Calculates:
        - Accuracy: Overall correctness
        - Precision: True positives / (True positives + False positives)
        - Recall: True positives / (True positives + False negatives)
        - F1-score: Harmonic mean of precision and recall
        - ROC-AUC: Area under ROC curve
        
        Args:
            X_test: Test features
            y_test: Test target
            
        Returns:
            Dict with comprehensive metrics
        """
        logger.info("Evaluating ensemble on holdout test set...")
        
        # Get predictions
        y_pred = self.trainer.ensemble.predict(X_test)
        y_pred_proba = self.trainer.ensemble.predict_proba(X_test)[:, 1]
        
        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1_score': f1_score(y_test, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_test, y_pred_proba),
            'test_size': len(y_test),
            'positive_rate': y_test.mean()
        }
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        metrics['confusion_matrix'] = cm.tolist()
        
        logger.info(f"Test set metrics: {metrics}")
        
        return metrics
    
    def compare_performance(self, validation_metrics: Dict, test_metrics: Dict) -> Dict:
        """
        Compare test vs validation performance.
        
        Calculates degradation for each metric and flags overfitting if
        degradation exceeds 20% threshold.
        
        Args:
            validation_metrics: Metrics from validation set
            test_metrics: Metrics from test set
            
        Returns:
            Dict with comparison results and overfitting flag
        """
        logger.info("Comparing test vs validation performance...")
        
        comparison = {}
        metrics_to_compare = ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']
        
        for metric in metrics_to_compare:
            val_value = validation_metrics.get(metric, 0)
            test_value = test_metrics.get(metric, 0)
            
            # Calculate degradation percentage
            if val_value > 0:
                degradation_pct = ((val_value - test_value) / val_value) * 100
            else:
                degradation_pct = 0
            
            comparison[metric] = {
                'validation': val_value,
                'test': test_value,
                'degradation_pct': degradation_pct,
                'degraded': degradation_pct > 20
            }
        
        # Overall overfitting flag
        overfitting_detected = any(
            comp['degraded'] for comp in comparison.values()
        )
        
        comparison['overfitting_detected'] = overfitting_detected
        comparison['max_degradation_pct'] = max(
            comp['degradation_pct'] for comp in comparison.values()
            if isinstance(comp, dict)
        )
        
        if overfitting_detected:
            logger.warning(f"⚠️  OVERFITTING DETECTED! Max degradation: {comparison['max_degradation_pct']:.1f}%")
        else:
            logger.info(f"✓ No overfitting detected. Max degradation: {comparison['max_degradation_pct']:.1f}%")
        
        return comparison
    
    def generate_feature_importance(self, feature_names: list) -> Dict:
        """
        Generate feature importance report from ensemble models.
        
        Extracts feature importance from Random Forest and XGBoost models,
        averages them, and ranks features by importance.
        
        Args:
            feature_names: List of feature names
            
        Returns:
            Dict with feature importance rankings
        """
        logger.info("Generating feature importance report...")
        
        importance_dict = {}
        
        # Get importance from Random Forest
        if 'random_forest' in self.trainer.models:
            rf_importance = self.trainer.models['random_forest'].feature_importances_
            importance_dict['random_forest'] = dict(zip(feature_names, rf_importance))
        
        # Get importance from XGBoost
        if 'xgboost' in self.trainer.models:
            xgb_importance = self.trainer.models['xgboost'].feature_importances_
            importance_dict['xgboost'] = dict(zip(feature_names, xgb_importance))
        
        # Average importance across models
        avg_importance = {}
        for feature in feature_names:
            importances = []
            if 'random_forest' in importance_dict:
                importances.append(importance_dict['random_forest'][feature])
            if 'xgboost' in importance_dict:
                importances.append(importance_dict['xgboost'][feature])
            
            avg_importance[feature] = np.mean(importances) if importances else 0
        
        # Sort by importance
        sorted_features = sorted(
            avg_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Create report
        report = {
            'top_10_features': sorted_features[:10],
            'all_features': sorted_features,
            'model_specific': importance_dict
        }
        
        logger.info("Top 10 most important features:")
        for i, (feature, importance) in enumerate(sorted_features[:10], 1):
            logger.info(f"  {i}. {feature}: {importance:.4f}")
        
        return report
    
    def plot_confusion_matrix(self, cm: np.ndarray, output_file: str) -> None:
        """
        Plot confusion matrix.
        
        Args:
            cm: Confusion matrix array
            output_file: Path to save plot
        """
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm,
            annot=True,
            fmt='d',
            cmap='Blues',
            xticklabels=['Negative', 'Positive'],
            yticklabels=['Negative', 'Positive']
        )
        plt.title('Confusion Matrix - Test Set')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.savefig(output_file)
        logger.info(f"Confusion matrix saved to {output_file}")
        plt.close()
    
    def plot_feature_importance(self, importance_report: Dict, output_file: str) -> None:
        """
        Plot top feature importances.
        
        Args:
            importance_report: Feature importance report
            output_file: Path to save plot
        """
        top_features = importance_report['top_10_features']
        features = [f[0] for f in top_features]
        importances = [f[1] for f in top_features]
        
        plt.figure(figsize=(10, 6))
        plt.barh(range(len(features)), importances)
        plt.yticks(range(len(features)), features)
        plt.xlabel('Importance')
        plt.title('Top 10 Feature Importances')
        plt.tight_layout()
        plt.savefig(output_file)
        logger.info(f"Feature importance plot saved to {output_file}")
        plt.close()
    
    def generate_report(self, output_dir: str = "ml_validation_reports") -> Dict:
        """
        Generate comprehensive validation report.
        
        Report includes:
        - Test set metrics
        - Validation vs test comparison
        - Overfitting detection
        - Feature importance rankings
        - Confusion matrix
        
        Args:
            output_dir: Directory to save report files
            
        Returns:
            Dict with complete validation results
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create report
        report = {
            'timestamp': timestamp,
            'test_metrics': self.test_metrics,
            'validation_metrics': self.validation_metrics,
            'performance_comparison': self.comparison,
            'feature_importance': self.importance_report,
            'overfitting_detected': self.comparison['overfitting_detected'],
            'max_degradation_pct': self.comparison['max_degradation_pct']
        }
        
        # Save JSON report (convert numpy types to native Python types)
        report_file = output_path / f"validation_report_{timestamp}.json"
        
        def convert_to_native(obj):
            """Convert numpy types to native Python types for JSON serialization."""
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(convert_to_native(item) for item in obj)
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            else:
                return obj
        
        report_serializable = convert_to_native(report)
        
        with open(report_file, 'w') as f:
            json.dump(report_serializable, f, indent=2)
        logger.info(f"Validation report saved to {report_file}")
        
        # Plot confusion matrix
        cm = np.array(self.test_metrics['confusion_matrix'])
        cm_file = output_path / f"confusion_matrix_{timestamp}.png"
        self.plot_confusion_matrix(cm, str(cm_file))
        
        # Plot feature importance
        fi_file = output_path / f"feature_importance_{timestamp}.png"
        self.plot_feature_importance(self.importance_report, str(fi_file))
        
        # Generate text summary
        summary_file = output_path / f"validation_summary_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("ML MODEL OUT-OF-SAMPLE VALIDATION REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Test Set Size: {self.test_metrics['test_size']}\n")
            f.write(f"Positive Rate: {self.test_metrics['positive_rate']:.3f}\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("TEST SET METRICS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Accuracy:  {self.test_metrics['accuracy']:.4f}\n")
            f.write(f"Precision: {self.test_metrics['precision']:.4f}\n")
            f.write(f"Recall:    {self.test_metrics['recall']:.4f}\n")
            f.write(f"F1-Score:  {self.test_metrics['f1_score']:.4f}\n")
            f.write(f"ROC-AUC:   {self.test_metrics['roc_auc']:.4f}\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("VALIDATION VS TEST COMPARISON\n")
            f.write("-" * 80 + "\n")
            for metric in ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']:
                comp = self.comparison[metric]
                f.write(f"{metric.upper()}:\n")
                f.write(f"  Validation: {comp['validation']:.4f}\n")
                f.write(f"  Test:       {comp['test']:.4f}\n")
                f.write(f"  Degradation: {comp['degradation_pct']:.1f}%")
                if comp['degraded']:
                    f.write(" ⚠️  EXCEEDS 20% THRESHOLD")
                f.write("\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("OVERFITTING DETECTION\n")
            f.write("-" * 80 + "\n")
            if self.comparison['overfitting_detected']:
                f.write("⚠️  OVERFITTING DETECTED!\n")
                f.write(f"Max degradation: {self.comparison['max_degradation_pct']:.1f}%\n")
                f.write("Recommendation: Consider retraining with more data or regularization\n\n")
            else:
                f.write("✓ No overfitting detected\n")
                f.write(f"Max degradation: {self.comparison['max_degradation_pct']:.1f}%\n")
                f.write("Model generalizes well to unseen data\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("TOP 10 MOST IMPORTANT FEATURES\n")
            f.write("-" * 80 + "\n")
            for i, (feature, importance) in enumerate(self.importance_report['top_10_features'], 1):
                f.write(f"{i:2d}. {feature:30s} {importance:.4f}\n")
            
            f.write("\n" + "=" * 80 + "\n")
        
        logger.info(f"Validation summary saved to {summary_file}")
        
        return report
    
    def run_validation(self, load_validation_metrics: bool = True) -> Dict:
        """
        Run complete out-of-sample validation pipeline.
        
        Steps:
        1. Load feature data
        2. Load trained models
        3. Split data (70% train, 15% val, 15% test)
        4. Evaluate on test set
        5. Compare to validation performance
        6. Generate feature importance
        7. Create comprehensive report
        
        Args:
            load_validation_metrics: Whether to load validation metrics from training
            
        Returns:
            Dict with validation results
        """
        logger.info("=" * 80)
        logger.info("STARTING OUT-OF-SAMPLE VALIDATION")
        logger.info("=" * 80)
        
        # Load data
        features, target = self.load_data()
        
        # Load models
        self.load_models()
        
        # Initialize trainer with actual data for splitting
        self.trainer.features = features
        self.trainer.target = target
        
        # Split data (same as training: 70% train, 15% val, 15% test)
        X_train, X_val, X_test, y_train, y_val, y_test = self.trainer.split_data()
        
        # Load validation metrics if available
        if load_validation_metrics:
            metadata_file = self.feature_file.replace('.parquet', '_metadata.json').replace('.csv', '_metadata.json')
            if Path(metadata_file).exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    if 'validation_metrics' in metadata:
                        self.validation_metrics = metadata['validation_metrics']
                        logger.info("Loaded validation metrics from metadata")
        
        # If validation metrics not available, evaluate on validation set
        if self.validation_metrics is None:
            logger.info("Validation metrics not found, evaluating on validation set...")
            self.validation_metrics = self.trainer.evaluate_model(
                self.trainer.ensemble, X_val, y_val
            )
        
        # Evaluate on test set (holdout)
        self.test_metrics = self.evaluate_on_test_set(X_test, y_test)
        
        # Compare performance
        self.comparison = self.compare_performance(
            self.validation_metrics,
            self.test_metrics
        )
        
        # Generate feature importance
        self.importance_report = self.generate_feature_importance(
            list(features.columns)
        )
        
        # Generate comprehensive report
        report = self.generate_report()
        
        logger.info("=" * 80)
        logger.info("OUT-OF-SAMPLE VALIDATION COMPLETE")
        logger.info("=" * 80)
        
        return report


def main():
    """Main execution function."""
    # Configuration
    feature_file = "ml_data/ml_features_20260216_011349.parquet"
    model_dir = "ml_models"
    
    # Create validator
    validator = OutOfSampleValidator(feature_file, model_dir)
    
    # Run validation
    report = validator.run_validation()
    
    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Test Accuracy:  {report['test_metrics']['accuracy']:.4f}")
    print(f"Test Precision: {report['test_metrics']['precision']:.4f}")
    print(f"Test Recall:    {report['test_metrics']['recall']:.4f}")
    print(f"Test F1-Score:  {report['test_metrics']['f1_score']:.4f}")
    print(f"Test ROC-AUC:   {report['test_metrics']['roc_auc']:.4f}")
    print()
    print(f"Max Degradation: {report['max_degradation_pct']:.1f}%")
    
    if report['overfitting_detected']:
        print("⚠️  OVERFITTING DETECTED - Model may not generalize well")
    else:
        print("✓ No overfitting detected - Model generalizes well")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
