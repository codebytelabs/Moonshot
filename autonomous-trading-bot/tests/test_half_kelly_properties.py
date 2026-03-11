"""
Property-based tests for half-Kelly position sizing in RiskManager.

Feature: bot-optimization-validation
Properties: 47, 48, 49, 50
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

from src.risk_manager import RiskManager


# ── Helper Functions ───────────────────────────────────────────────────

def create_mock_settings():
    """Create mock settings for RiskManager."""
    s = MagicMock()
    s.max_positions = 5
    s.max_risk_per_trade_pct = 0.02
    s.max_portfolio_exposure_pct = 0.50
    s.max_single_exposure_pct = 0.15
    s.max_correlation = 0.7
    s.max_drawdown_pct = 0.20
    s.daily_loss_limit_pct = 0.05
    s.initial_equity_usd = 10000.0
    return s


def create_risk_manager():
    """Create RiskManager instance."""
    return RiskManager(create_mock_settings())


def create_mock_store_with_trades():
    """Create mock SupabaseStore with historical trades."""
    store = MagicMock()
    
    def get_recent_trades(n=1000):
        """Return mock trades with varying PnL."""
        now = datetime.now(timezone.utc)
        trades = []
        
        # Create 50 trades over last 90 days
        for i in range(50):
            trade_time = now - timedelta(days=i * 1.8)  # Spread over 90 days
            
            # 55% win rate
            pnl = 100.0 if i % 100 < 55 else -80.0
            
            trades.append({
                'created_at': trade_time.isoformat(),
                'pnl': pnl,
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'price': 50000.0,
                'quantity': 0.01,
                'notional_usd': 500.0,
                'trade_type': 'entry'
            })
        
        return trades
    
    store.get_recent_trades = get_recent_trades
    return store


# ── Property 47: Half-Kelly Calculation ────────────────────────────────

@given(
    win_rate=st.floats(min_value=0.4, max_value=0.8),
    avg_win_loss_ratio=st.floats(min_value=0.5, max_value=3.0),
    equity=st.floats(min_value=1000.0, max_value=100000.0),
    entry_price=st.floats(min_value=100.0, max_value=100000.0),
    stop_loss_pct=st.floats(min_value=0.01, max_value=0.10)
)
@settings(max_examples=100, deadline=None)
def test_property_47_half_kelly_calculation(
    win_rate, avg_win_loss_ratio, equity, entry_price, stop_loss_pct
):
    """
    Feature: bot-optimization-validation, Property 47: Half-Kelly calculation
    
    For any trade opportunity, position size fraction should be calculated as
    f = 0.5 × (p × (b + 1) - 1) / b, where p is win_rate and b is avg_win/avg_loss
    
    Validates: Requirements 23.1, 23.2
    """
    # Setup
    risk_manager = create_risk_manager()
    mock_store = create_mock_store_with_trades()
    
    risk_manager.equity = equity
    risk_manager.set_store(mock_store)
    
    # Manually set Kelly parameters (simulating sufficient trade history)
    risk_manager.kelly_win_rate = win_rate
    risk_manager.kelly_avg_win_loss_ratio = avg_win_loss_ratio
    risk_manager.kelly_trade_count = 50
    risk_manager.kelly_last_update = datetime.now()
    
    # Calculate position size
    stop_loss = entry_price * (1 - stop_loss_pct)
    size_usd = risk_manager.position_size_usd(entry_price, stop_loss)
    
    # Calculate expected half-Kelly fraction
    p = win_rate
    b = avg_win_loss_ratio
    full_kelly = (p * (b + 1) - 1) / b
    half_kelly = 0.5 * full_kelly
    
    # If Kelly is negative or capped, position should reflect that
    if half_kelly <= 0:
        assert size_usd == 0.0, "Negative Kelly should result in zero position size"
    else:
        # Calculate expected position size
        kelly_fraction = min(half_kelly, risk_manager.max_kelly_fraction)
        risk_per_unit = stop_loss_pct
        expected_size = (equity * kelly_fraction) / risk_per_unit
        
        # Cap at max single exposure
        max_size = equity * risk_manager.max_single_exposure_pct
        expected_size = min(expected_size, max_size)
        
        # Allow for rounding and constraint adjustments (within 10%)
        if expected_size > 0:
            assert size_usd <= expected_size * 1.1, \
                f"Position size {size_usd} exceeds expected {expected_size}"


# ── Property 48: Kelly Fraction Cap ────────────────────────────────────

@given(
    win_rate=st.floats(min_value=0.6, max_value=0.9),
    avg_win_loss_ratio=st.floats(min_value=2.0, max_value=5.0),
    equity=st.floats(min_value=5000.0, max_value=50000.0)
)
@settings(max_examples=100, deadline=None)
def test_property_48_kelly_fraction_cap(
    win_rate, avg_win_loss_ratio, equity
):
    """
    Feature: bot-optimization-validation, Property 48: Kelly fraction cap
    
    For any calculated Kelly fraction, if it exceeds 0.25, position size should
    be capped at 25% of equity.
    
    Validates: Requirements 23.3
    """
    # Setup with parameters that will produce high Kelly
    risk_manager = create_risk_manager()
    mock_store = create_mock_store_with_trades()
    
    risk_manager.equity = equity
    risk_manager.set_store(mock_store)
    risk_manager.kelly_win_rate = win_rate
    risk_manager.kelly_avg_win_loss_ratio = avg_win_loss_ratio
    risk_manager.kelly_trade_count = 50
    risk_manager.kelly_last_update = datetime.now()
    
    # Calculate Kelly fraction
    kelly_fraction = risk_manager.calculate_half_kelly_fraction()
    
    # Should be capped at 0.25
    assert kelly_fraction <= 0.25, \
        f"Kelly fraction {kelly_fraction} exceeds cap of 0.25"
    
    # Calculate position size with tight stop (1% risk)
    entry_price = 50000.0
    stop_loss = entry_price * 0.99
    size_usd = risk_manager.position_size_usd(entry_price, stop_loss)
    
    # Position size should not exceed what 25% Kelly would produce
    risk_per_unit = 0.01
    max_kelly_size = (equity * 0.25) / risk_per_unit
    
    # Cap at max single exposure
    max_single = equity * risk_manager.max_single_exposure_pct
    max_expected = min(max_kelly_size, max_single)
    
    assert size_usd <= max_expected * 1.01, \
        f"Position size {size_usd} exceeds max Kelly cap {max_expected}"


# ── Property 49: Negative Kelly Rejection ──────────────────────────────

@given(
    win_rate=st.floats(min_value=0.1, max_value=0.45),
    avg_win_loss_ratio=st.floats(min_value=0.3, max_value=1.0),
    equity=st.floats(min_value=5000.0, max_value=50000.0)
)
@settings(max_examples=100, deadline=None)
def test_property_49_negative_kelly_rejection(
    win_rate, avg_win_loss_ratio, equity
):
    """
    Feature: bot-optimization-validation, Property 49: Negative Kelly rejection
    
    For any calculated Kelly fraction, if it is negative, the trade opportunity
    should be rejected (position size = 0).
    
    Validates: Requirements 23.4
    """
    # Setup with parameters that will produce negative Kelly
    risk_manager = create_risk_manager()
    mock_store = create_mock_store_with_trades()
    
    risk_manager.equity = equity
    risk_manager.set_store(mock_store)
    risk_manager.kelly_win_rate = win_rate
    risk_manager.kelly_avg_win_loss_ratio = avg_win_loss_ratio
    risk_manager.kelly_trade_count = 50
    risk_manager.kelly_last_update = datetime.now()
    
    # Calculate Kelly fraction
    p = win_rate
    b = avg_win_loss_ratio
    full_kelly = (p * (b + 1) - 1) / b
    half_kelly = 0.5 * full_kelly
    
    # If Kelly is negative, position size should be zero
    if half_kelly < 0:
        kelly_fraction = risk_manager.calculate_half_kelly_fraction()
        assert kelly_fraction == 0.0, \
            f"Negative Kelly should return 0, got {kelly_fraction}"
        
        # Position size should also be zero
        entry_price = 50000.0
        stop_loss = entry_price * 0.98
        size_usd = risk_manager.position_size_usd(entry_price, stop_loss)
        
        assert size_usd == 0.0, \
            f"Negative Kelly should result in zero position size, got {size_usd}"


# ── Property 50: Position Size Constraints ─────────────────────────────

@given(
    win_rate=st.floats(min_value=0.5, max_value=0.7),
    avg_win_loss_ratio=st.floats(min_value=1.0, max_value=2.5),
    equity=st.floats(min_value=10000.0, max_value=50000.0),
    entry_price=st.floats(min_value=1000.0, max_value=50000.0),
    stop_loss_pct=st.floats(min_value=0.02, max_value=0.08),
    existing_exposure_pct=st.floats(min_value=0.0, max_value=0.40)
)
@settings(max_examples=100, deadline=None)
def test_property_50_position_size_constraints(
    win_rate, avg_win_loss_ratio, equity, entry_price, stop_loss_pct,
    existing_exposure_pct
):
    """
    Feature: bot-optimization-validation, Property 50: Position size constraints
    
    For any calculated position size, it should respect all constraints:
    - max_single_exposure_pct (15%)
    - max_portfolio_exposure_pct (50%)
    - remaining_exposure_capacity
    
    Validates: Requirements 23.7, 23.8
    """
    # Setup
    risk_manager = create_risk_manager()
    mock_store = create_mock_store_with_trades()
    
    risk_manager.equity = equity
    risk_manager.set_store(mock_store)
    risk_manager.kelly_win_rate = win_rate
    risk_manager.kelly_avg_win_loss_ratio = avg_win_loss_ratio
    risk_manager.kelly_trade_count = 50
    risk_manager.kelly_last_update = datetime.now()
    
    # Add existing positions to simulate portfolio exposure
    existing_notional = equity * existing_exposure_pct
    risk_manager.open_positions = [
        {'symbol': 'ETH/USDT', 'notional_usd': existing_notional}
    ]
    
    # Calculate position size
    stop_loss = entry_price * (1 - stop_loss_pct)
    size_usd = risk_manager.position_size_usd(entry_price, stop_loss)
    
    # Constraint 1: Max single exposure
    max_single = equity * risk_manager.max_single_exposure_pct
    assert size_usd <= max_single * 1.01, \
        f"Position size {size_usd} exceeds max single exposure {max_single}"
    
    # Constraint 2: Max portfolio exposure
    total_exposure = existing_notional + size_usd
    max_portfolio = equity * risk_manager.max_portfolio_exposure_pct
    assert total_exposure <= max_portfolio * 1.01, \
        f"Total exposure {total_exposure} exceeds max portfolio {max_portfolio}"
    
    # Constraint 3: Remaining capacity
    remaining_capacity = max_portfolio - existing_notional
    assert size_usd <= remaining_capacity * 1.01, \
        f"Position size {size_usd} exceeds remaining capacity {remaining_capacity}"


# ── Unit Tests for Kelly Parameter Updates ─────────────────────────────

def test_kelly_parameters_insufficient_trades():
    """
    With <30 trades, should use conservative default (0.10).
    
    Validates: Requirements 23.6
    """
    risk_manager = create_risk_manager()
    
    # Mock store with only 20 trades
    store = MagicMock()
    now = datetime.now(timezone.utc)
    trades = []
    for i in range(20):
        trade_time = now - timedelta(days=i * 4)
        trades.append({
            'created_at': trade_time.isoformat(),
            'pnl': 50.0 if i % 2 == 0 else -40.0,
            'symbol': 'BTC/USDT'
        })
    store.get_recent_trades = lambda n: trades
    
    risk_manager.set_store(store)
    risk_manager.update_kelly_parameters(force=True)
    
    # Should use conservative default
    kelly_fraction = risk_manager.calculate_half_kelly_fraction()
    assert kelly_fraction == risk_manager.conservative_default_fraction, \
        f"Expected conservative default {risk_manager.conservative_default_fraction}, got {kelly_fraction}"


def test_kelly_parameters_sufficient_trades():
    """
    With ≥30 trades, should calculate Kelly from historical data.
    
    Validates: Requirements 23.5, 23.6
    """
    risk_manager = create_risk_manager()
    mock_store = create_mock_store_with_trades()
    
    risk_manager.set_store(mock_store)
    risk_manager.update_kelly_parameters(force=True)
    
    # Should have calculated parameters
    assert risk_manager.kelly_win_rate is not None
    assert risk_manager.kelly_avg_win_loss_ratio is not None
    assert risk_manager.kelly_trade_count >= 30
    
    # Kelly fraction should be calculated (not default)
    kelly_fraction = risk_manager.calculate_half_kelly_fraction()
    assert kelly_fraction > 0


def test_kelly_parameters_monthly_update():
    """
    Kelly parameters should update monthly.
    
    Validates: Requirements 23.5
    """
    risk_manager = create_risk_manager()
    mock_store = create_mock_store_with_trades()
    
    risk_manager.set_store(mock_store)
    
    # First update
    risk_manager.update_kelly_parameters(force=True)
    first_update = risk_manager.kelly_last_update
    
    # Try to update immediately (should skip)
    risk_manager.update_kelly_parameters(force=False)
    assert risk_manager.kelly_last_update == first_update
    
    # Simulate 31 days passing
    risk_manager.kelly_last_update = datetime.now() - timedelta(days=31)
    risk_manager.update_kelly_parameters(force=False)
    
    # Should have updated
    assert risk_manager.kelly_last_update > first_update


def test_kelly_parameters_no_store():
    """
    Without store, should handle gracefully and use defaults.
    
    Validates: Requirements 23.6
    """
    risk_manager = create_risk_manager()
    
    # No store set
    risk_manager.update_kelly_parameters(force=True)
    
    # Should use conservative default
    kelly_fraction = risk_manager.calculate_half_kelly_fraction()
    assert kelly_fraction == risk_manager.conservative_default_fraction
