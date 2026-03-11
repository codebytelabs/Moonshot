"""
Example script demonstrating OnlineLearningPipeline usage

This script shows how to:
1. Load trained models
2. Initialize the online learning pipeline
3. Accumulate trade outcomes
4. Trigger incremental updates
5. Validate and rollback if needed
6. Schedule full retraining
"""

import sys
import os
import asyncio
import pandas as pd
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from online_learning_pipeline import OnlineLearningPipeline
from ml_model_trainer import MLModelTrainer


async def main():
    """Demonstrate online learning pipeline usage"""
    
    print("=" * 80)
    print("Online Learning Pipeline Example")
    print("=" * 80)
    
    # Step 1: Load or train base models
    print("\n1. Loading/Training base models...")
    
    # For this example, we'll create sample data and train models
    np.random.seed(42)
    n_samples = 500
    
    features = pd.DataFrame({
        'ta_score': np.random.uniform(50, 90, n_samples),
        'volume_spike': np.random.uniform(0, 1, n_samples),
        'sentiment_score': np.random.uniform(0, 1, n_samples),
        'volatility_percentile': np.random.uniform(0, 1, n_samples),
        'trend_strength': np.random.uniform(0, 1, n_samples)
    })
    
    # Create target: success if ta_score > 70 and sentiment_score > 0.5
    target = pd.Series([
        1 if (features.loc[i, 'ta_score'] > 70 and features.loc[i, 'sentiment_score'] > 0.5) else 0
        for i in range(n_samples)
    ])
    
    print(f"   Training data: {len(features)} samples")
    print(f"   Positive rate: {target.mean():.2%}")
    
    # Train models
    trainer = MLModelTrainer(features, target)
    training_results = trainer.train_all_models()
    
    print(f"   ✓ Models trained successfully")
    print(f"   Ensemble validation accuracy: {training_results['validation_metrics']['ensemble']['accuracy']:.4f}")
    
    # Step 2: Initialize online learning pipeline
    print("\n2. Initializing online learning pipeline...")
    
    # Include ensemble in models dict
    models_with_ensemble = {
        **training_results['models'],
        'ensemble': training_results['ensemble']
    }
    
    pipeline = OnlineLearningPipeline(
        base_models=models_with_ensemble,
        update_threshold=50,
        rolling_window=1000,
        validation_window=100,
        degradation_threshold=0.10,
        retrain_interval_days=90
    )
    
    print(f"   ✓ Pipeline initialized")
    print(f"   Update threshold: {pipeline.update_threshold}")
    print(f"   Rolling window: {pipeline.rolling_window}")
    print(f"   Validation window: {pipeline.validation_window}")
    
    # Step 3: Simulate accumulating trade outcomes
    print("\n3. Simulating trade outcome accumulation...")
    
    # Simulate 75 new trades
    for i in range(75):
        # Generate random features for new trade
        new_features = {
            'ta_score': np.random.uniform(50, 90),
            'volume_spike': np.random.uniform(0, 1),
            'sentiment_score': np.random.uniform(0, 1),
            'volatility_percentile': np.random.uniform(0, 1),
            'trend_strength': np.random.uniform(0, 1)
        }
        
        # Simulate outcome (success if ta_score > 70 and sentiment_score > 0.5)
        outcome = (new_features['ta_score'] > 70 and new_features['sentiment_score'] > 0.5)
        
        # Accumulate outcome
        pipeline.accumulate_trade_outcome(new_features, outcome)
        
        if (i + 1) % 25 == 0:
            print(f"   Accumulated {i + 1} trade outcomes...")
    
    status = pipeline.get_status()
    print(f"   ✓ Accumulated {status['new_outcomes_count']} outcomes")
    print(f"   Buffer size: {status['buffer_size']}")
    print(f"   Should update: {status['should_update']}")
    
    # Step 4: Trigger incremental update
    if pipeline.should_update():
        print("\n4. Triggering incremental update...")
        
        update_result = await pipeline.incremental_update()
        
        if update_result['success']:
            print(f"   ✓ Update successful!")
            print(f"   New model version: {update_result['model_version']}")
            print(f"   Training samples: {update_result['training_samples']}")
            print(f"   Validation passed: {update_result['validation_passed']}")
        else:
            print(f"   ✗ Update failed")
            print(f"   Reason: {update_result.get('reason', 'Unknown')}")
            if 'error' in update_result:
                print(f"   Error: {update_result['error']}")
    else:
        print("\n4. Update threshold not reached yet")
        print(f"   Need {pipeline.update_threshold - status['new_outcomes_count']} more outcomes")
    
    # Step 5: Check performance history
    print("\n5. Performance history...")
    
    if len(pipeline.performance_history) > 0:
        latest_metrics = pipeline.performance_history[-1]
        print(f"   Latest validation metrics:")
        print(f"   - Previous accuracy: {latest_metrics['prev_accuracy']:.4f}")
        print(f"   - New accuracy: {latest_metrics['new_accuracy']:.4f}")
        print(f"   - Performance change: {latest_metrics['performance_change']:+.2%}")
        print(f"   - Degradation: {latest_metrics['degradation']:.2%}")
    else:
        print("   No performance history yet")
    
    # Step 6: Check full retrain schedule
    print("\n6. Full retraining schedule...")
    
    schedule_info = pipeline.schedule_full_retrain()
    print(f"   Last full retrain: {schedule_info['last_full_retrain'].date()}")
    print(f"   Next retrain date: {schedule_info['next_retrain_date'].date()}")
    print(f"   Days until retrain: {schedule_info['days_until_retrain']}")
    print(f"   Should retrain now: {schedule_info['should_retrain_now']}")
    
    # Step 7: Save pipeline state
    print("\n7. Saving pipeline state...")
    
    output_dir = "ml_models/online_learning"
    pipeline.save_pipeline_state(output_dir)
    print(f"   ✓ Pipeline state saved to {output_dir}")
    
    # Step 8: Final status
    print("\n8. Final pipeline status...")
    
    final_status = pipeline.get_status()
    print(f"   Model version: {final_status['model_version']}")
    print(f"   Buffer size: {final_status['buffer_size']}")
    print(f"   New outcomes count: {final_status['new_outcomes_count']}")
    print(f"   Performance history entries: {final_status['performance_history_length']}")
    
    print("\n" + "=" * 80)
    print("Example completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
