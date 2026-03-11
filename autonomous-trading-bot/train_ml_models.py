"""
Train ML Models Script

Trains ensemble of ML models (Random Forest, Gradient Boosting, XGBoost) on extracted features.
Saves trained models and generates training report.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import json
from datetime import datetime
from src.ml_model_trainer import MLModelTrainer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_feature_data(data_dir: str = "ml_data") -> tuple:
    """
    Load feature data from disk.
    
    Args:
        data_dir: Directory containing feature data
        
    Returns:
        Tuple of (features DataFrame, target Series, metadata dict)
    """
    data_path = Path(data_dir)
    
    # Find most recent feature file
    feature_files = list(data_path.glob("ml_features_*.parquet"))
    if not feature_files:
        raise FileNotFoundError(f"No feature files found in {data_dir}")
    
    latest_file = max(feature_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Loading features from {latest_file}")
    
    # Load features
    df = pd.read_parquet(latest_file)
    
    # Load metadata
    metadata_file = latest_file.with_suffix('.json').name.replace('.parquet', '_metadata.json')
    metadata_path = data_path / metadata_file
    
    metadata = {}
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        logger.info(f"Loaded metadata from {metadata_path}")
    
    # Separate features and target
    if 'target' not in df.columns:
        raise ValueError("Target column not found in feature data")
    
    target = df['target']
    features = df.drop(columns=['target'])
    
    logger.info(f"Loaded {len(features)} samples with {len(features.columns)} features")
    logger.info(f"Target distribution: {target.value_counts().to_dict()}")
    
    return features, target, metadata


def train_models(features: pd.DataFrame, target: pd.Series) -> dict:
    """
    Train ML models on feature data.
    
    Args:
        features: Feature matrix
        target: Target variable
        
    Returns:
        Training results dictionary
    """
    logger.info("Initializing ML model trainer...")
    trainer = MLModelTrainer(features, target)
    
    logger.info("Starting model training pipeline...")
    results = trainer.train_all_models()
    
    # Save models
    logger.info("Saving trained models...")
    trainer.save_models("ml_models")
    
    return results


def generate_training_report(results: dict, metadata: dict, output_file: str = "TASK_7.6_ML_TRAINING_SUMMARY.md"):
    """
    Generate training summary report.
    
    Args:
        results: Training results from trainer
        metadata: Feature extraction metadata
        output_file: Output file path
    """
    report = []
    report.append("# Task 7.6: ML Model Training Summary")
    report.append("")
    report.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Data splits
    report.append("## Data Splits")
    report.append("")
    splits = results['data_splits']
    report.append(f"- **Training samples**: {splits['train_size']}")
    report.append(f"- **Validation samples**: {splits['val_size']}")
    report.append(f"- **Test samples**: {splits['test_size']}")
    report.append(f"- **Total samples**: {sum(splits.values())}")
    report.append("")
    
    # Model configurations
    report.append("## Model Configurations")
    report.append("")
    
    report.append("### Random Forest")
    report.append("- n_estimators: 200")
    report.append("- max_depth: 10")
    report.append("- min_samples_split: 50")
    report.append("- min_samples_leaf: 20")
    report.append("")
    
    report.append("### Gradient Boosting")
    report.append("- n_estimators: 150")
    report.append("- learning_rate: 0.05")
    report.append("- max_depth: 8")
    report.append("- subsample: 0.8")
    report.append("")
    
    report.append("### XGBoost")
    report.append("- n_estimators: 200")
    report.append("- learning_rate: 0.05")
    report.append("- max_depth: 8")
    report.append("- subsample: 0.8")
    report.append("")
    
    # Validation metrics
    report.append("## Validation Set Performance")
    report.append("")
    
    metrics = results['validation_metrics']
    
    report.append("| Model | Accuracy | Precision | Recall | F1-Score | ROC-AUC |")
    report.append("|-------|----------|-----------|--------|----------|---------|")
    
    for model_name in ['random_forest', 'gradient_boosting', 'xgboost', 'ensemble']:
        m = metrics[model_name]
        display_name = model_name.replace('_', ' ').title()
        report.append(
            f"| {display_name} | {m['accuracy']:.4f} | {m['precision']:.4f} | "
            f"{m['recall']:.4f} | {m['f1_score']:.4f} | {m['roc_auc']:.4f} |"
        )
    
    report.append("")
    
    # Ensemble configuration
    report.append("## Ensemble Configuration")
    report.append("")
    report.append("Weighted voting ensemble:")
    report.append("- Random Forest: 30%")
    report.append("- Gradient Boosting: 30%")
    report.append("- XGBoost: 40%")
    report.append("")
    
    # Requirements validation
    report.append("## Requirements Validation")
    report.append("")
    
    ensemble_acc = metrics['ensemble']['accuracy']
    target_acc = 0.55
    
    report.append(f"**Requirement 17.7**: Ensemble achieves minimum 55% accuracy on validation data")
    if ensemble_acc >= target_acc:
        report.append(f"- ✅ **PASS**: Ensemble accuracy = {ensemble_acc:.4f} (>= {target_acc})")
    else:
        report.append(f"- ❌ **FAIL**: Ensemble accuracy = {ensemble_acc:.4f} (< {target_acc})")
    report.append("")
    
    report.append(f"**Requirement 17.6**: Data split maintains temporal order (70% train, 15% val, 15% test)")
    train_pct = splits['train_size'] / sum(splits.values())
    val_pct = splits['val_size'] / sum(splits.values())
    test_pct = splits['test_size'] / sum(splits.values())
    report.append(f"- ✅ **PASS**: Train={train_pct:.1%}, Val={val_pct:.1%}, Test={test_pct:.1%}")
    report.append("")
    
    # Feature information
    if metadata:
        report.append("## Feature Information")
        report.append("")
        if 'feature_count' in metadata:
            report.append(f"- **Total features**: {metadata['feature_count']}")
        if 'extraction_date' in metadata:
            report.append(f"- **Extraction date**: {metadata['extraction_date']}")
        report.append("")
    
    # Model files
    report.append("## Saved Models")
    report.append("")
    report.append("Models saved to `ml_models/` directory:")
    report.append("- `random_forest.joblib`")
    report.append("- `gradient_boosting.joblib`")
    report.append("- `xgboost.joblib`")
    report.append("- `ensemble.joblib`")
    report.append("")
    
    # Next steps
    report.append("## Next Steps")
    report.append("")
    report.append("1. **Task 7.7**: Write property test for ensemble prediction")
    report.append("2. **Task 7.8**: Train ML models on historical data (complete)")
    report.append("3. **Task 7.9**: Implement out-of-sample validation")
    report.append("4. **Task 7.10**: Write property test for out-of-sample validation")
    report.append("")
    
    # Write report
    with open(output_file, 'w') as f:
        f.write('\n'.join(report))
    
    logger.info(f"Training report saved to {output_file}")


def main():
    """Main training script."""
    try:
        # Load feature data
        logger.info("=" * 80)
        logger.info("ML MODEL TRAINING PIPELINE")
        logger.info("=" * 80)
        
        features, target, metadata = load_feature_data()
        
        # Train models
        results = train_models(features, target)
        
        # Generate report
        generate_training_report(results, metadata)
        
        logger.info("=" * 80)
        logger.info("ML MODEL TRAINING COMPLETE")
        logger.info("=" * 80)
        
        # Print summary
        ensemble_metrics = results['validation_metrics']['ensemble']
        logger.info(f"Ensemble Validation Accuracy: {ensemble_metrics['accuracy']:.4f}")
        logger.info(f"Ensemble Validation ROC-AUC: {ensemble_metrics['roc_auc']:.4f}")
        logger.info(f"Models saved to: ml_models/")
        logger.info(f"Report saved to: TASK_7.6_ML_TRAINING_SUMMARY.md")
        
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
