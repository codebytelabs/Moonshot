# Task 7.6: ML Model Training Summary

**Date**: 2026-02-16 01:29:48

## Data Splits

- **Training samples**: 70
- **Validation samples**: 15
- **Test samples**: 15
- **Total samples**: 100

## Model Configurations

### Random Forest
- n_estimators: 200
- max_depth: 10
- min_samples_split: 50
- min_samples_leaf: 20

### Gradient Boosting
- n_estimators: 150
- learning_rate: 0.05
- max_depth: 8
- subsample: 0.8

### XGBoost
- n_estimators: 200
- learning_rate: 0.05
- max_depth: 8
- subsample: 0.8

## Validation Set Performance

| Model | Accuracy | Precision | Recall | F1-Score | ROC-AUC |
|-------|----------|-----------|--------|----------|---------|
| Random Forest | 0.4667 | 0.0000 | 0.0000 | 0.0000 | 0.9464 |
| Gradient Boosting | 0.7333 | 0.7500 | 0.7500 | 0.7500 | 0.9107 |
| Xgboost | 0.4667 | 0.0000 | 0.0000 | 0.0000 | 0.9643 |
| Ensemble | 0.4667 | 0.0000 | 0.0000 | 0.0000 | 0.9286 |

## Ensemble Configuration

Weighted voting ensemble:
- Random Forest: 30%
- Gradient Boosting: 30%
- XGBoost: 40%

## Requirements Validation

**Requirement 17.7**: Ensemble achieves minimum 55% accuracy on validation data
- ❌ **FAIL**: Ensemble accuracy = 0.4667 (< 0.55)

**Requirement 17.6**: Data split maintains temporal order (70% train, 15% val, 15% test)
- ✅ **PASS**: Train=70.0%, Val=15.0%, Test=15.0%

## Saved Models

Models saved to `ml_models/` directory:
- `random_forest.joblib`
- `gradient_boosting.joblib`
- `xgboost.joblib`
- `ensemble.joblib`

## Next Steps

1. **Task 7.7**: Write property test for ensemble prediction
2. **Task 7.8**: Train ML models on historical data (complete)
3. **Task 7.9**: Implement out-of-sample validation
4. **Task 7.10**: Write property test for out-of-sample validation
