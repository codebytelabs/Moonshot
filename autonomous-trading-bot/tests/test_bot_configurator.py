"""
Unit tests for OptimizedBotConfigurator

Tests the configuration loading and application functionality.
"""
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from configure_optimized_bot import OptimizedBotConfigurator


@pytest.fixture
def sample_optimization_report():
    """Create a sample optimization report."""
    return """
================================================================================
PARAMETER OPTIMIZATION REPORT
================================================================================

1. BAYESIAN THRESHOLD OPTIMIZATION
--------------------------------------------------------------------------------
Optimal Threshold: 0.5
Composite Score: 17.7000
Total Trades: 50
Win Rate: 55.00%
Profit Factor: 2.00
Sharpe Ratio: 1.50

2. TRAILING STOP OPTIMIZATION
--------------------------------------------------------------------------------
Optimal Stop: 15%
Avg R-Multiple: 5.90
Runner Trades: 15
% Above 5R: 66.7%

3. TIMEFRAME WEIGHT OPTIMIZATION
--------------------------------------------------------------------------------
Optimal Weights:
  5m:  0.10
  15m: 0.21
  1h:  0.30
  4h:  0.39
Win Rate: 55.00%
Composite Score: 17.7000

4. CONTEXT AGENT A/B TEST
--------------------------------------------------------------------------------
Recommendation: ENABLE
Alpha Improvement: $+100.00
Win Rate Delta: +3.00%
Profit Factor Delta: +0.10
Cost-Benefit Ratio: 200.00

================================================================================
OPTIMIZATION COMPLETE
================================================================================
"""


@pytest.fixture
def temp_optimization_report(sample_optimization_report):
    """Create a temporary optimization report file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write(sample_optimization_report)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
        f.write("# Test environment file\n")
        f.write("EXISTING_KEY=existing_value\n")
        f.write("BAYESIAN_THRESHOLD_NORMAL=0.65\n")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_ml_models_dir():
    """Create a temporary ML models directory."""
    import tempfile
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    
    temp_dir = tempfile.mkdtemp()
    
    # Create dummy models
    dummy_model = RandomForestClassifier(n_estimators=10, random_state=42)
    
    for model_name in ['random_forest', 'gradient_boosting', 'xgboost', 'ensemble']:
        model_path = Path(temp_dir) / f"{model_name}.joblib"
        joblib.dump(dummy_model, model_path)
    
    yield temp_dir
    
    # Cleanup
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


class TestOptimizedBotConfigurator:
    """Test suite for OptimizedBotConfigurator."""
    
    def test_initialization(self, temp_optimization_report, temp_ml_models_dir):
        """Test configurator initialization."""
        configurator = OptimizedBotConfigurator(
            optimization_report_path=temp_optimization_report,
            ml_models_dir=temp_ml_models_dir
        )
        
        assert configurator.optimization_report_path.exists()
        assert configurator.ml_models_dir.exists()
        assert configurator.optimized_params == {}
    
    def test_load_optimization_results(self, temp_optimization_report, temp_ml_models_dir):
        """Test loading optimization results from report."""
        configurator = OptimizedBotConfigurator(
            optimization_report_path=temp_optimization_report,
            ml_models_dir=temp_ml_models_dir
        )
        
        params = configurator.load_optimization_results()
        
        # Verify Bayesian threshold (Requirement 11.8)
        assert 'bayesian_threshold' in params
        assert params['bayesian_threshold'] == 0.5
        
        # Verify trailing stop (Requirement 12.7)
        assert 'trailing_stop_pct' in params
        assert params['trailing_stop_pct'] == 0.15
        
        # Verify timeframe weights (Requirement 13.8)
        assert 'timeframe_weights' in params
        assert params['timeframe_weights']['5m'] == 0.10
        assert params['timeframe_weights']['15m'] == 0.21
        assert params['timeframe_weights']['1h'] == 0.30
        assert params['timeframe_weights']['4h'] == 0.39
        
        # Verify Context Agent (Requirement 14.8)
        assert 'context_agent_enabled' in params
        assert params['context_agent_enabled'] is True
    
    def test_load_optimization_results_missing_file(self, temp_ml_models_dir):
        """Test error handling when optimization report is missing."""
        configurator = OptimizedBotConfigurator(
            optimization_report_path="nonexistent_file.txt",
            ml_models_dir=temp_ml_models_dir
        )
        
        with pytest.raises(FileNotFoundError):
            configurator.load_optimization_results()
    
    def test_validate_ml_models(self, temp_optimization_report, temp_ml_models_dir):
        """Test ML model validation (Requirement 20.2)."""
        configurator = OptimizedBotConfigurator(
            optimization_report_path=temp_optimization_report,
            ml_models_dir=temp_ml_models_dir
        )
        
        validation_results = configurator.validate_ml_models()
        
        # All models should be valid
        assert validation_results['random_forest.joblib'] is True
        assert validation_results['gradient_boosting.joblib'] is True
        assert validation_results['xgboost.joblib'] is True
        assert validation_results['ensemble.joblib'] is True
    
    def test_validate_ml_models_missing(self, temp_optimization_report):
        """Test ML model validation with missing models."""
        with tempfile.TemporaryDirectory() as temp_dir:
            configurator = OptimizedBotConfigurator(
                optimization_report_path=temp_optimization_report,
                ml_models_dir=temp_dir
            )
            
            validation_results = configurator.validate_ml_models()
            
            # All models should be invalid (missing)
            assert validation_results['random_forest.joblib'] is False
            assert validation_results['gradient_boosting.joblib'] is False
            assert validation_results['xgboost.joblib'] is False
            assert validation_results['ensemble.joblib'] is False
    
    def test_generate_config_dict(self, temp_optimization_report, temp_ml_models_dir):
        """Test configuration dictionary generation."""
        configurator = OptimizedBotConfigurator(
            optimization_report_path=temp_optimization_report,
            ml_models_dir=temp_ml_models_dir
        )
        
        config = configurator.generate_config_dict()
        
        # Verify Bayesian threshold (Requirement 11.8)
        assert config['bayesian_threshold_normal'] == 0.5
        
        # Verify trailing stop (Requirement 12.7)
        assert config['runner_trailing_stop_pct'] == 0.15
        
        # Verify timeframe weights (Requirement 13.8)
        assert config['timeframe_weights']['5m'] == 0.10
        assert config['timeframe_weights']['15m'] == 0.21
        assert config['timeframe_weights']['1h'] == 0.30
        assert config['timeframe_weights']['4h'] == 0.39
        
        # Verify Context Agent (Requirement 14.8)
        assert config['context_agent_enabled'] is True
        
        # Verify ML configuration (Requirement 20.2)
        assert config['ml_enabled'] is True
        assert 'ml_models_dir' in config
        
        # Verify half-Kelly configuration (Requirement 20.3)
        assert config['position_sizing_method'] == 'half_kelly'
        assert config['kelly_fraction'] == 0.5
        assert config['max_kelly_fraction'] == 0.25
        assert config['min_trades_for_kelly'] == 30
        assert config['kelly_default_fraction'] == 0.10
    
    def test_update_env_file(self, temp_optimization_report, temp_ml_models_dir, temp_env_file):
        """Test .env file update."""
        configurator = OptimizedBotConfigurator(
            optimization_report_path=temp_optimization_report,
            ml_models_dir=temp_ml_models_dir,
            env_file_path=temp_env_file
        )
        
        configurator.load_optimization_results()
        configurator.update_env_file()
        
        # Read updated .env file
        with open(temp_env_file, 'r') as f:
            content = f.read()
        
        # Verify key parameters are present
        assert 'BAYESIAN_THRESHOLD_NORMAL=0.5' in content
        assert 'RUNNER_TRAILING_STOP_PCT=0.15' in content
        assert 'CONTEXT_AGENT_ENABLED=true' in content
        assert 'ML_ENABLED=true' in content
        assert 'POSITION_SIZING_METHOD=half_kelly' in content
        
        # Verify existing key is preserved
        assert 'EXISTING_KEY=existing_value' in content
    
    def test_generate_config_file(self, temp_optimization_report, temp_ml_models_dir):
        """Test JSON configuration file generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_config.json"
            
            configurator = OptimizedBotConfigurator(
                optimization_report_path=temp_optimization_report,
                ml_models_dir=temp_ml_models_dir
            )
            
            # Override base_dir for testing
            configurator.base_dir = Path(temp_dir)
            
            configurator.load_optimization_results()
            configurator.generate_config_file(output_path="test_config.json")
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify content
            with open(output_path, 'r') as f:
                config = json.load(f)
            
            assert config['bayesian_threshold_normal'] == 0.5
            assert config['runner_trailing_stop_pct'] == 0.15
            assert config['context_agent_enabled'] is True
            assert config['ml_enabled'] is True
            assert config['position_sizing_method'] == 'half_kelly'
    
    def test_configure_bot_complete(self, temp_optimization_report, temp_ml_models_dir, temp_env_file):
        """Test complete bot configuration process."""
        with tempfile.TemporaryDirectory() as temp_dir:
            configurator = OptimizedBotConfigurator(
                optimization_report_path=temp_optimization_report,
                ml_models_dir=temp_ml_models_dir,
                env_file_path=temp_env_file
            )
            
            # Override base_dir for testing
            configurator.base_dir = Path(temp_dir)
            
            config = configurator.configure_bot(
                update_env=True,
                generate_json=True,
                validate_models=True
            )
            
            # Verify configuration was generated
            assert config is not None
            assert 'bayesian_threshold_normal' in config
            assert 'runner_trailing_stop_pct' in config
            assert 'timeframe_weights' in config
            assert 'context_agent_enabled' in config
            assert 'ml_enabled' in config
            assert 'position_sizing_method' in config
            
            # Verify JSON file was created
            json_path = Path(temp_dir) / "optimized_config.json"
            assert json_path.exists()
    
    def test_context_agent_disable_recommendation(self, temp_ml_models_dir):
        """Test Context Agent disable recommendation (Requirement 14.8)."""
        # Create report with DISABLE recommendation
        report_content = """
4. CONTEXT AGENT A/B TEST
--------------------------------------------------------------------------------
Recommendation: DISABLE
Alpha Improvement: $+10.00
Win Rate Delta: +1.00%
"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(report_content)
            temp_path = f.name
        
        try:
            configurator = OptimizedBotConfigurator(
                optimization_report_path=temp_path,
                ml_models_dir=temp_ml_models_dir
            )
            
            params = configurator.load_optimization_results()
            
            # Verify Context Agent is disabled
            assert params['context_agent_enabled'] is False
        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_default_values_on_missing_params(self, temp_ml_models_dir):
        """Test default values are used when parameters are missing."""
        # Create minimal report
        report_content = "PARAMETER OPTIMIZATION REPORT\n"
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(report_content)
            temp_path = f.name
        
        try:
            configurator = OptimizedBotConfigurator(
                optimization_report_path=temp_path,
                ml_models_dir=temp_ml_models_dir
            )
            
            config = configurator.generate_config_dict()
            
            # Verify defaults are used
            assert config['bayesian_threshold_normal'] == 0.65  # Default
            assert config['runner_trailing_stop_pct'] == 0.25  # Default
            assert 'timeframe_weights' in config  # Default weights
            assert config['context_agent_enabled'] is True  # Default
        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
