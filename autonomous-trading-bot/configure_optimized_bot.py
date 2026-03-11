#!/usr/bin/env python3
"""
Configure Bot with Optimized Parameters

This script loads optimal parameters from optimization results and configures
the bot for extended validation or live deployment.

Requirements: 11.8, 12.7, 13.8, 14.8, 20.2, 20.3
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
import joblib


class OptimizedBotConfigurator:
    """Load and apply optimized parameters to bot configuration."""
    
    def __init__(
        self,
        optimization_report_path: str = "optimization_results/parameter_optimization_report.txt",
        ml_models_dir: str = "ml_models",
        env_file_path: str = "../.env"
    ):
        """
        Initialize configurator with paths to optimization results.
        
        Args:
            optimization_report_path: Path to parameter optimization report
            ml_models_dir: Directory containing trained ML models
            env_file_path: Path to .env file to update
        """
        self.base_dir = Path(__file__).parent
        self.optimization_report_path = self.base_dir / optimization_report_path
        self.ml_models_dir = self.base_dir / ml_models_dir
        self.env_file_path = Path(env_file_path).resolve()
        
        self.optimized_params: Dict[str, Any] = {}
        
    def load_optimization_results(self) -> Dict[str, Any]:
        """
        Load optimal parameters from optimization report.
        
        Returns:
            Dictionary containing all optimized parameters
        """
        if not self.optimization_report_path.exists():
            raise FileNotFoundError(
                f"Optimization report not found: {self.optimization_report_path}"
            )
        
        with open(self.optimization_report_path, 'r') as f:
            content = f.read()
        
        params = {}
        
        # Parse Bayesian threshold
        threshold_match = re.search(r'Optimal Threshold:\s+([\d.]+)', content)
        if threshold_match:
            params['bayesian_threshold'] = float(threshold_match.group(1))
        
        # Parse trailing stop
        stop_match = re.search(r'Optimal Stop:\s+([\d.]+)%', content)
        if stop_match:
            params['trailing_stop_pct'] = float(stop_match.group(1)) / 100.0
        
        # Parse timeframe weights
        weights = {}
        for tf in ['5m', '15m', '1h', '4h']:
            weight_match = re.search(rf'{tf}:\s+([\d.]+)', content)
            if weight_match:
                weights[tf] = float(weight_match.group(1))
        if weights:
            params['timeframe_weights'] = weights
        
        # Parse Context Agent recommendation
        context_match = re.search(r'Recommendation:\s+(\w+)', content)
        if context_match:
            params['context_agent_enabled'] = context_match.group(1).upper() == 'ENABLE'
        
        self.optimized_params = params
        return params
    
    def validate_ml_models(self) -> Dict[str, bool]:
        """
        Validate that all required ML models are present and loadable.
        
        Returns:
            Dictionary with model names and validation status
        """
        required_models = [
            'random_forest.joblib',
            'gradient_boosting.joblib',
            'xgboost.joblib',
            'ensemble.joblib'
        ]
        
        validation_results = {}
        
        for model_name in required_models:
            model_path = self.ml_models_dir / model_name
            try:
                if model_path.exists():
                    # Try to load the model
                    model = joblib.load(model_path)
                    validation_results[model_name] = True
                    print(f"✓ {model_name} loaded successfully")
                else:
                    validation_results[model_name] = False
                    print(f"✗ {model_name} not found")
            except Exception as e:
                validation_results[model_name] = False
                print(f"✗ {model_name} failed to load: {e}")
        
        return validation_results
    
    def generate_config_dict(self) -> Dict[str, Any]:
        """
        Generate complete configuration dictionary with optimized parameters.
        
        Returns:
            Configuration dictionary ready for bot initialization
        """
        if not self.optimized_params:
            self.load_optimization_results()
        
        config = {
            # Bayesian threshold (Requirement 11.8)
            'bayesian_threshold_normal': self.optimized_params.get('bayesian_threshold', 0.65),
            
            # Trailing stop (Requirement 12.7)
            'runner_trailing_stop_pct': self.optimized_params.get('trailing_stop_pct', 0.25),
            
            # Timeframe weights (Requirement 13.8)
            'timeframe_weights': self.optimized_params.get('timeframe_weights', {
                '5m': 0.10,
                '15m': 0.20,
                '1h': 0.30,
                '4h': 0.40
            }),
            
            # Context Agent (Requirement 14.8)
            'context_agent_enabled': self.optimized_params.get('context_agent_enabled', True),
            
            # ML models (Requirement 20.2)
            'ml_enabled': True,
            'ml_models_dir': str(self.ml_models_dir),
            
            # Half-Kelly position sizing (Requirement 20.3)
            'position_sizing_method': 'half_kelly',
            'kelly_fraction': 0.5,
            'max_kelly_fraction': 0.25,
            'min_trades_for_kelly': 30,
            'kelly_default_fraction': 0.10,
            'kelly_update_frequency_days': 30,
            'kelly_lookback_days': 90,
        }
        
        return config
    
    def update_env_file(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Update .env file with optimized parameters.
        
        Args:
            config: Configuration dictionary (if None, generates from optimized params)
        """
        if config is None:
            config = self.generate_config_dict()
        
        # Read existing .env file
        env_lines = []
        if self.env_file_path.exists():
            with open(self.env_file_path, 'r') as f:
                env_lines = f.readlines()
        
        # Update or add configuration values
        updates = {
            'BAYESIAN_THRESHOLD_NORMAL': str(config['bayesian_threshold_normal']),
            'RUNNER_TRAILING_STOP_PCT': str(config['runner_trailing_stop_pct']),
            'CONTEXT_AGENT_ENABLED': str(config['context_agent_enabled']).lower(),
            'ML_ENABLED': str(config['ml_enabled']).lower(),
            'ML_MODELS_DIR': config['ml_models_dir'],
            'POSITION_SIZING_METHOD': config['position_sizing_method'],
            'KELLY_FRACTION': str(config['kelly_fraction']),
            'MAX_KELLY_FRACTION': str(config['max_kelly_fraction']),
        }
        
        # Update existing lines or collect new ones
        updated_keys = set()
        for i, line in enumerate(env_lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            key = line.split('=')[0].strip()
            if key in updates:
                env_lines[i] = f"{key}={updates[key]}\n"
                updated_keys.add(key)
        
        # Add new keys that weren't in the file
        for key, value in updates.items():
            if key not in updated_keys:
                env_lines.append(f"{key}={value}\n")
        
        # Write back to .env file
        with open(self.env_file_path, 'w') as f:
            f.writelines(env_lines)
        
        print(f"\n✓ Updated {self.env_file_path} with optimized parameters")
    
    def generate_config_file(self, output_path: str = "optimized_config.json") -> None:
        """
        Generate a JSON configuration file with all optimized parameters.
        
        Args:
            output_path: Path to save the configuration file
        """
        config = self.generate_config_dict()
        
        output_file = self.base_dir / output_path
        with open(output_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✓ Generated configuration file: {output_file}")
    
    def print_configuration_summary(self) -> None:
        """Print a summary of the optimized configuration."""
        if not self.optimized_params:
            self.load_optimization_results()
        
        config = self.generate_config_dict()
        
        print("\n" + "="*80)
        print("OPTIMIZED BOT CONFIGURATION SUMMARY")
        print("="*80)
        
        print("\n1. BAYESIAN DECISION THRESHOLD (Requirement 11.8)")
        print(f"   Optimal Threshold: {config['bayesian_threshold_normal']:.2f}")
        
        print("\n2. TRAILING STOP PERCENTAGE (Requirement 12.7)")
        print(f"   Optimal Stop: {config['runner_trailing_stop_pct']*100:.1f}%")
        
        print("\n3. TIMEFRAME WEIGHTS (Requirement 13.8)")
        for tf, weight in config['timeframe_weights'].items():
            print(f"   {tf:>3}: {weight:.2f}")
        
        print("\n4. CONTEXT AGENT (Requirement 14.8)")
        status = "ENABLED" if config['context_agent_enabled'] else "DISABLED"
        print(f"   Status: {status}")
        
        print("\n5. ML MODELS (Requirement 20.2)")
        print(f"   ML Enabled: {config['ml_enabled']}")
        print(f"   Models Directory: {config['ml_models_dir']}")
        
        print("\n6. HALF-KELLY POSITION SIZING (Requirement 20.3)")
        print(f"   Method: {config['position_sizing_method']}")
        print(f"   Kelly Fraction: {config['kelly_fraction']}")
        print(f"   Max Kelly Fraction: {config['max_kelly_fraction']}")
        print(f"   Min Trades for Kelly: {config['min_trades_for_kelly']}")
        print(f"   Default Fraction: {config['kelly_default_fraction']}")
        
        print("\n" + "="*80)
    
    def configure_bot(
        self,
        update_env: bool = True,
        generate_json: bool = True,
        validate_models: bool = True
    ) -> Dict[str, Any]:
        """
        Complete bot configuration process.
        
        Args:
            update_env: Whether to update .env file
            generate_json: Whether to generate JSON config file
            validate_models: Whether to validate ML models
        
        Returns:
            Configuration dictionary
        """
        print("Starting bot configuration with optimized parameters...")
        print("="*80)
        
        # Load optimization results
        print("\n1. Loading optimization results...")
        self.load_optimization_results()
        print(f"✓ Loaded {len(self.optimized_params)} optimized parameters")
        
        # Validate ML models
        if validate_models:
            print("\n2. Validating ML models...")
            validation_results = self.validate_ml_models()
            all_valid = all(validation_results.values())
            if not all_valid:
                print("⚠ Warning: Some ML models are missing or invalid")
            else:
                print("✓ All ML models validated successfully")
        
        # Generate configuration
        print("\n3. Generating configuration...")
        config = self.generate_config_dict()
        print("✓ Configuration generated")
        
        # Update .env file
        if update_env:
            print("\n4. Updating .env file...")
            self.update_env_file(config)
        
        # Generate JSON config file
        if generate_json:
            print("\n5. Generating JSON configuration file...")
            self.generate_config_file()
        
        # Print summary
        self.print_configuration_summary()
        
        print("\n✓ Bot configuration complete!")
        print("="*80)
        
        return config


def main():
    """Main entry point for configuration script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Configure bot with optimized parameters"
    )
    parser.add_argument(
        '--no-env-update',
        action='store_true',
        help="Skip updating .env file"
    )
    parser.add_argument(
        '--no-json',
        action='store_true',
        help="Skip generating JSON config file"
    )
    parser.add_argument(
        '--no-validation',
        action='store_true',
        help="Skip ML model validation"
    )
    parser.add_argument(
        '--optimization-report',
        default="optimization_results/parameter_optimization_report.txt",
        help="Path to optimization report"
    )
    parser.add_argument(
        '--ml-models-dir',
        default="ml_models",
        help="Directory containing ML models"
    )
    
    args = parser.parse_args()
    
    # Create configurator
    configurator = OptimizedBotConfigurator(
        optimization_report_path=args.optimization_report,
        ml_models_dir=args.ml_models_dir
    )
    
    # Configure bot
    try:
        config = configurator.configure_bot(
            update_env=not args.no_env_update,
            generate_json=not args.no_json,
            validate_models=not args.no_validation
        )
        
        print("\n✓ Configuration successful!")
        print("\nNext steps:")
        print("  1. Review the optimized_config.json file")
        print("  2. Verify .env file has been updated")
        print("  3. Run extended validation: python run_extended_validation.py")
        
        return 0
    
    except Exception as e:
        print(f"\n✗ Configuration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
