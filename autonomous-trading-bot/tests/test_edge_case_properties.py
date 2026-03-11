"""
Property-based tests for Edge Case Identification and Circuit Breaker.

Tests universal properties that should hold for all valid inputs.
Uses hypothesis library for property-based testing.

**Validates: Requirements 22.2, 22.6**
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime
from unittest.mock import Mock, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from extended_validation_system import (
    ExtendedValidationSystem,
    EdgeCase
)


# Strategies for generating test data

@st.composite
def edge_case_data(draw):
    """Generate valid edge case data."""
    # Valid categories per Requirement 22.2
    category = draw(st.sampled_from([
        'data_quality',
        'logic_error',
        'market_anomaly',
        'API_failure'
    ]))
    
    description = draw(st.text(min_size=10, max_size=200))
    
    # Generate context dictionary
    context_keys = draw(st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))),
        min_size=1,
        max_size=5,
        unique=True
    ))
    
    context = {}
    for key in context_keys:
        value = draw(st.one_of(
            st.text(min_size=1, max_size=50),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans()
        ))
        context[key] = value
    
    return category, description, context


@st.composite
def trade_sequence(draw):
    """Generate a sequence of trades with PnL values."""
    num_trades = draw(st.integers(min_value=1, max_value=20))
    
    trades = []
    for i in range(num_trades):
        pnl = draw(st.floats(
            min_value=-1000,
            max_value=1000,
            allow_nan=False,
            allow_infinity=False
        ))
        
        trades.append({
            'id': f'trade_{i}',
            'symbol': 'BTC/USDT',
            'pnl': pnl,
            'r_multiple': pnl / 100 if pnl != 0 else 0,
            'timestamp': datetime.now().isoformat()
        })
    
    return trades


@st.composite
def consecutive_failure_sequence(draw):
    """Generate a sequence with exactly 3 consecutive failures."""
    # Generate some successful trades before failures
    num_before = draw(st.integers(min_value=0, max_value=5))
    
    trades = []
    
    # Add successful trades
    for i in range(num_before):
        trades.append({
            'id': f'trade_{i}',
            'pnl': draw(st.floats(min_value=1, max_value=1000, allow_nan=False, allow_infinity=False))
        })
    
    # Add exactly 3 consecutive failures
    for i in range(3):
        trades.append({
            'id': f'trade_{num_before + i}',
            'pnl': draw(st.floats(min_value=-1000, max_value=-1, allow_nan=False, allow_infinity=False))
        })
    
    # Optionally add more trades after
    num_after = draw(st.integers(min_value=0, max_value=5))
    for i in range(num_after):
        pnl = draw(st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False))
        trades.append({
            'id': f'trade_{num_before + 3 + i}',
            'pnl': pnl
        })
    
    return trades


# Fixtures

@pytest.fixture
def mock_bot():
    """Create mock trading bot."""
    bot = Mock()
    bot.config = {'bayesian_threshold': 0.65}
    return bot


@pytest.fixture
def mock_exchange():
    """Create mock exchange connector."""
    exchange = Mock()
    return exchange


@pytest.fixture
def mock_store():
    """Create mock Supabase store."""
    store = Mock()
    store.client = MagicMock()
    
    # Mock table operations
    mock_table = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock()
    mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
    mock_insert.execute.return_value = mock_execute
    mock_table.insert.return_value = mock_insert
    store.client.table.return_value = mock_table
    
    store.get_recent_trades = Mock(return_value=[])
    store.get_open_positions = Mock(return_value=[])
    store.insert_performance_metric = Mock(return_value={'id': 'metric123'})
    
    return store


@pytest.fixture
def validation_system(mock_bot, mock_exchange, mock_store):
    """Create ExtendedValidationSystem instance."""
    return ExtendedValidationSystem(
        bot=mock_bot,
        exchange=mock_exchange,
        store=mock_store,
        duration_days=28
    )


class TestEdgeCaseProperties:
    """Property-based tests for edge case identification."""
    
    @given(edge_case_data())
    @settings(max_examples=5, deadline=None)
    def test_property_45_edge_case_categorization(self, ec_data):
        """
        **Property 45: Edge case categorization**
        **Validates: Requirements 22.2**
        
        Property: For any identified edge case, it should be categorized as one of:
        data_quality, logic_error, market_anomaly, or API_failure
        
        This test verifies that all edge cases are properly categorized.
        """
        category, description, context = ec_data
        
        # Create validation system
        mock_bot = Mock()
        mock_exchange = Mock()
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
        mock_insert.execute.return_value = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_store.client.table.return_value = mock_table
        
        validation_system = ExtendedValidationSystem(
            bot=mock_bot,
            exchange=mock_exchange,
            store=mock_store,
            duration_days=28
        )
        
        # Log the edge case
        validation_system._log_edge_case(
            category=category,
            description=description,
            context=context
        )
        
        # Verify edge case was logged
        assert len(validation_system.edge_cases) == 1
        
        logged_edge_case = validation_system.edge_cases[0]
        
        # Property: Category must be one of the valid categories
        valid_categories = ['data_quality', 'logic_error', 'market_anomaly', 'API_failure']
        assert logged_edge_case.category in valid_categories, (
            f"Edge case category '{logged_edge_case.category}' must be one of {valid_categories}"
        )
        
        # Verify other fields are preserved
        assert logged_edge_case.description == description
        assert logged_edge_case.context == context
        assert logged_edge_case.resolution_status == "open"
        assert isinstance(logged_edge_case.timestamp, datetime)
    
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=5, deadline=None)
    def test_property_45_invalid_category_handling(self, invalid_category):
        """
        **Property 45: Edge case categorization (invalid input handling)**
        **Validates: Requirements 22.2**
        
        Property: When an invalid category is provided, the system should handle it
        gracefully by defaulting to a valid category.
        """
        # Assume the category is NOT one of the valid ones
        valid_categories = ['data_quality', 'logic_error', 'market_anomaly', 'API_failure']
        assume(invalid_category not in valid_categories)
        
        # Create validation system
        mock_bot = Mock()
        mock_exchange = Mock()
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
        mock_insert.execute.return_value = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_store.client.table.return_value = mock_table
        
        validation_system = ExtendedValidationSystem(
            bot=mock_bot,
            exchange=mock_exchange,
            store=mock_store,
            duration_days=28
        )
        
        # Log edge case with invalid category
        validation_system._log_edge_case(
            category=invalid_category,
            description="Test edge case",
            context={'test': 'data'}
        )
        
        # Verify edge case was logged with a valid category (fallback)
        assert len(validation_system.edge_cases) == 1
        logged_edge_case = validation_system.edge_cases[0]
        
        # Property: Even with invalid input, the logged category must be valid
        assert logged_edge_case.category in valid_categories, (
            f"System must ensure edge case category is valid, got '{logged_edge_case.category}'"
        )
    
    @given(edge_case_data())
    @settings(max_examples=5, deadline=None)
    def test_property_45_edge_case_frequency_tracking(self, ec_data):
        """
        **Property 45: Edge case categorization (frequency tracking)**
        **Validates: Requirements 22.2, 22.4**
        
        Property: The system should track frequency of each edge case type.
        """
        category, description, context = ec_data
        
        # Create validation system
        mock_bot = Mock()
        mock_exchange = Mock()
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
        mock_insert.execute.return_value = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_store.client.table.return_value = mock_table
        
        validation_system = ExtendedValidationSystem(
            bot=mock_bot,
            exchange=mock_exchange,
            store=mock_store,
            duration_days=28
        )
        
        # Log multiple edge cases of the same category
        num_cases = 3
        for i in range(num_cases):
            validation_system._log_edge_case(
                category=category,
                description=f"{description}_{i}",
                context=context
            )
        
        # Get edge case summary
        summary = validation_system._summarize_edge_cases()
        
        # Property: Frequency should be tracked correctly
        assert summary['total_count'] == num_cases
        assert summary['by_category'][category] == num_cases
        
        # Property: All categories should be valid
        for cat in summary['by_category'].keys():
            assert cat in ['data_quality', 'logic_error', 'market_anomaly', 'API_failure']


class TestCircuitBreakerProperties:
    """Property-based tests for circuit breaker functionality."""
    
    @given(consecutive_failure_sequence())
    @settings(max_examples=5, deadline=None)
    def test_property_46_circuit_breaker_trigger(self, trade_list):
        """
        **Property 46: Circuit breaker trigger**
        **Validates: Requirements 22.6**
        
        Property: For any sequence of trades, if 3 consecutive trades fail,
        circuit breaker should pause trading.
        
        This test verifies the circuit breaker triggers after exactly 3 consecutive failures.
        """
        # Create validation system
        mock_bot = Mock()
        mock_exchange = Mock()
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
        mock_insert.execute.return_value = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_store.client.table.return_value = mock_table
        
        validation_system = ExtendedValidationSystem(
            bot=mock_bot,
            exchange=mock_exchange,
            store=mock_store,
            duration_days=28
        )
        
        # Process trades one by one
        for i, trade in enumerate(trade_list):
            validation_system.record_trade_result(trade)
            
            # Count consecutive failures up to this point
            consecutive_failures = 0
            for j in range(i, -1, -1):
                if trade_list[j]['pnl'] < 0:
                    consecutive_failures += 1
                else:
                    break
            
            # Property: Circuit breaker should be active if and only if
            # we have 3 or more consecutive failures
            if consecutive_failures >= 3:
                assert validation_system.circuit_breaker_active, (
                    f"Circuit breaker should be active after {consecutive_failures} consecutive failures"
                )
                assert validation_system.is_trading_paused(), (
                    "Trading should be paused when circuit breaker is active"
                )
                
                # Property: Edge case should be logged
                circuit_breaker_edge_cases = [
                    ec for ec in validation_system.edge_cases
                    if "Circuit breaker" in ec.description
                ]
                assert len(circuit_breaker_edge_cases) >= 1, (
                    "Circuit breaker trigger should log an edge case"
                )
                
                # Property: Edge case should be categorized as logic_error
                for ec in circuit_breaker_edge_cases:
                    assert ec.category == "logic_error", (
                        "Circuit breaker edge case should be categorized as logic_error"
                    )
    
    @given(trade_sequence())
    @settings(max_examples=5, deadline=None)
    def test_property_46_circuit_breaker_reset_on_success(self, trade_list):
        """
        **Property 46: Circuit breaker reset behavior**
        **Validates: Requirements 22.6**
        
        Property: Consecutive failure counter should reset when a successful trade occurs.
        """
        # Create validation system
        mock_bot = Mock()
        mock_exchange = Mock()
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
        mock_insert.execute.return_value = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_store.client.table.return_value = mock_table
        
        validation_system = ExtendedValidationSystem(
            bot=mock_bot,
            exchange=mock_exchange,
            store=mock_store,
            duration_days=28
        )
        
        max_consecutive_seen = 0
        current_consecutive = 0
        
        for trade in trade_list:
            validation_system.record_trade_result(trade)
            
            if trade['pnl'] < 0:
                current_consecutive += 1
                max_consecutive_seen = max(max_consecutive_seen, current_consecutive)
            else:
                current_consecutive = 0
            
            # Property: If we haven't seen 3 consecutive failures yet,
            # circuit breaker should not be active
            if max_consecutive_seen < 3:
                assert not validation_system.circuit_breaker_active, (
                    f"Circuit breaker should not be active with only {max_consecutive_seen} "
                    f"consecutive failures (need 3)"
                )
    
    @given(consecutive_failure_sequence())
    @settings(max_examples=5, deadline=None)
    def test_property_46_circuit_breaker_requires_manual_reset(self, trade_list):
        """
        **Property 46: Circuit breaker manual reset requirement**
        **Validates: Requirements 22.7**
        
        Property: Once circuit breaker is triggered, it should require manual reset
        even if subsequent trades are successful.
        """
        # Create validation system
        mock_bot = Mock()
        mock_exchange = Mock()
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
        mock_insert.execute.return_value = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_store.client.table.return_value = mock_table
        
        validation_system = ExtendedValidationSystem(
            bot=mock_bot,
            exchange=mock_exchange,
            store=mock_store,
            duration_days=28
        )
        
        # Process all trades
        for trade in trade_list:
            validation_system.record_trade_result(trade)
        
        # If circuit breaker was triggered
        if validation_system.circuit_breaker_active:
            # Property: Circuit breaker should remain active until manual reset
            assert validation_system.is_trading_paused(), (
                "Circuit breaker should remain active until manual reset"
            )
            
            # Simulate successful trades - circuit breaker should still be active
            for _ in range(5):
                validation_system.record_trade_result({'pnl': 100.0})
            
            assert validation_system.circuit_breaker_active, (
                "Circuit breaker should remain active even after successful trades"
            )
            
            # Manual reset
            validation_system.reset_circuit_breaker("Manual review completed")
            
            # Property: After manual reset, circuit breaker should be inactive
            assert not validation_system.circuit_breaker_active, (
                "Circuit breaker should be inactive after manual reset"
            )
            assert not validation_system.is_trading_paused(), (
                "Trading should resume after manual reset"
            )
            assert validation_system.consecutive_failures == 0, (
                "Consecutive failures should be reset to 0"
            )
    
    @given(consecutive_failure_sequence())
    @settings(max_examples=5, deadline=None)
    def test_property_46_circuit_breaker_edge_case_resolution(self, trade_list):
        """
        **Property 46: Circuit breaker edge case resolution**
        **Validates: Requirements 22.5, 22.7**
        
        Property: When circuit breaker is reset, the associated edge case should
        be marked as resolved with resolution notes.
        """
        # Create validation system
        mock_bot = Mock()
        mock_exchange = Mock()
        mock_store = Mock()
        mock_store.client = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.execute.return_value = {'data': [{'id': 'test123'}]}
        mock_insert.execute.return_value = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_store.client.table.return_value = mock_table
        
        validation_system = ExtendedValidationSystem(
            bot=mock_bot,
            exchange=mock_exchange,
            store=mock_store,
            duration_days=28
        )
        
        # Process trades to trigger circuit breaker
        for trade in trade_list:
            validation_system.record_trade_result(trade)
        
        # If circuit breaker was triggered
        if validation_system.circuit_breaker_active:
            # Find the circuit breaker edge case
            cb_edge_cases_before = [
                ec for ec in validation_system.edge_cases
                if "Circuit breaker" in ec.description and ec.resolution_status == "open"
            ]
            
            assert len(cb_edge_cases_before) >= 1, (
                "Circuit breaker should create an open edge case"
            )
            
            # Reset with manual review notes
            review_notes = "Reviewed and approved to resume trading"
            validation_system.reset_circuit_breaker(review_notes)
            
            # Property: Edge case should be marked as resolved
            cb_edge_cases_after = [
                ec for ec in validation_system.edge_cases
                if "Circuit breaker" in ec.description and ec.resolution_status == "resolved"
            ]
            
            assert len(cb_edge_cases_after) >= 1, (
                "Circuit breaker edge case should be marked as resolved after reset"
            )
            
            # Property: Resolution notes should be recorded
            resolved_ec = cb_edge_cases_after[0]
            assert resolved_ec.resolution_notes is not None, (
                "Resolution notes should be recorded"
            )
            assert review_notes in resolved_ec.resolution_notes, (
                "Resolution notes should contain the manual review notes"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
