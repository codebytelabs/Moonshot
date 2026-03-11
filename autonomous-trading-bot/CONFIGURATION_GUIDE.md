# Bot Configuration Guide

## Quick Start

### 1. Configure Bot with Optimized Parameters

```bash
python configure_optimized_bot.py
```

This will:
- Load optimal parameters from `optimization_results/parameter_optimization_report.txt`
- Validate all ML models in `ml_models/`
- Update `.env` file with optimized parameters
- Generate `optimized_config.json` for review

### 2. Review Configuration

Check the generated configuration:

```bash
cat optimized_config.json
```

### 3. Verify Environment Variables

Ensure `.env` has been updated:

```bash
grep -E "BAYESIAN_THRESHOLD|TRAILING_STOP|CONTEXT_AGENT|ML_ENABLED|KELLY" ../.env
```

## Configuration Parameters

### Bayesian Decision Threshold
- **Parameter**: `bayesian_threshold_normal`
- **Optimal Value**: 0.50
- **Purpose**: Controls trade entry decisions in normal market mode
- **Requirement**: 11.8

### Trailing Stop Percentage
- **Parameter**: `runner_trailing_stop_pct`
- **Optimal Value**: 0.15 (15%)
- **Purpose**: Protects profits on runner positions
- **Requirement**: 12.7

### Timeframe Weights
- **Parameter**: `timeframe_weights`
- **Optimal Values**:
  - 5m: 0.10
  - 15m: 0.21
  - 1h: 0.30
  - 4h: 0.39
- **Purpose**: Balances trend identification from higher timeframes with precise entries from lower timeframes
- **Requirement**: 13.8

### Context Agent
- **Parameter**: `context_agent_enabled`
- **Optimal Value**: true
- **Purpose**: Enables LLM-powered sentiment and narrative analysis
- **Requirement**: 14.8

### ML Models
- **Parameter**: `ml_enabled`
- **Optimal Value**: true
- **Models Directory**: `ml_models/`
- **Purpose**: Enables ML ensemble for trade selection improvement
- **Requirement**: 20.2

### Half-Kelly Position Sizing
- **Parameter**: `position_sizing_method`
- **Value**: half_kelly
- **Kelly Fraction**: 0.5
- **Max Kelly Fraction**: 0.25
- **Purpose**: Optimal growth with safety margin
- **Requirement**: 20.3

## Advanced Usage

### Custom Optimization Report

```bash
python configure_optimized_bot.py \
  --optimization-report path/to/custom_report.txt
```

### Custom ML Models Directory

```bash
python configure_optimized_bot.py \
  --ml-models-dir path/to/custom_models
```

### Skip Environment File Update

```bash
python configure_optimized_bot.py --no-env-update
```

### Skip JSON Generation

```bash
python configure_optimized_bot.py --no-json
```

### Skip ML Model Validation

```bash
python configure_optimized_bot.py --no-validation
```

## Validation

### Check ML Models

```bash
ls -lh ml_models/
```

Expected files:
- `random_forest.joblib`
- `gradient_boosting.joblib`
- `xgboost.joblib`
- `ensemble.joblib`

### Test Configuration Loading

```python
from configure_optimized_bot import OptimizedBotConfigurator

configurator = OptimizedBotConfigurator()
config = configurator.generate_config_dict()
print(config)
```

## Integration with Bot

The configuration is automatically loaded by the bot through:

1. **Environment Variables**: Read from `.env` file
2. **Config Module**: `src/config.py` uses Pydantic Settings
3. **Runtime**: Bot components access via `get_settings()`

Example:
```python
from src.config import get_settings

settings = get_settings()
threshold = settings.bayesian_threshold_normal
trailing_stop = settings.runner_trailing_stop_pct
```

## Troubleshooting

### Missing Optimization Report

**Error**: `FileNotFoundError: Optimization report not found`

**Solution**: Run parameter optimization first:
```bash
python run_parameter_optimization.py
```

### Missing ML Models

**Error**: `ML models not found or invalid`

**Solution**: Train ML models first:
```bash
python train_ml_models.py
```

### Invalid Configuration Values

**Error**: Configuration values out of expected range

**Solution**: Check optimization report for valid values:
```bash
cat optimization_results/parameter_optimization_report.txt
```

## Next Steps

After configuration:

1. **Extended Validation**
   ```bash
   python run_extended_validation.py
   ```

2. **Monitor Performance**
   - Track metrics in real-time
   - Compare to backtest expectations

3. **Review Edge Cases**
   - Monitor edge case logs
   - Document and resolve issues

## Support

For issues or questions:
1. Check `TASK_9.10_BOT_CONFIGURATION_SUMMARY.md`
2. Review test suite: `tests/test_bot_configurator.py`
3. Examine configuration script: `configure_optimized_bot.py`
