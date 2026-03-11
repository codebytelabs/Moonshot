"""
Property-based tests for Position Manager tier exit execution.

These tests use hypothesis to verify universal properties hold across
all valid inputs, complementing the example-based unit tests.
"""
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch
import time

from src.position_manager import Position, PositionManager, PositionState
from src.config import Settings


# ── Test Data Strategies ────────────────────────────────────────────────

@st.composite
def open_position_at_2r(draw):
    """
    Generate an open position that has reached 2R profit (tier 1 target).
    
    The position should have:
    - entry_price and stop_loss such that risk is defined
    - current_price such that R-multiple >= 2.0
    - remaining_quantity = initial quantity (no exits yet)
    - tiers_exited = 0
    """
    entry_price = draw(st.floats(min_value=10.0, max_value=1000.0))
    # Risk should be reasonable (1-10% of entry)
    risk_pct = draw(st.floats(min_value=0.01, max_value=0.10))
    stop_loss = entry_price * (1 - risk_pct)
    
    # Calculate current price for slightly above 2R to avoid floating point issues
    risk = entry_price - stop_loss
    # Add a tiny bit more to ensure we're definitely >= 2.0
    current_price = entry_price + (2.001 * risk)
    
    # Use reasonable quantities that won't become 0 after 25% calculation
    # Minimum 0.1 to ensure 25% = 0.025 which is still meaningful
    quantity = draw(st.floats(min_value=0.1, max_value=10.0))
    
    position = Position(
        symbol="TEST/USDT",
        side="long",
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=entry_price + (5.0 * risk),  # 5R target
        setup_type="breakout",
        posterior=0.75,
    )
    
    # Set current price to achieve 2R+
    position.current_price = current_price
    position.highest_price = current_price
    
    return position


@st.composite
def open_position_above_2r(draw):
    """
    Generate an open position that has exceeded 2R profit.
    
    R-multiple should be >= 2.0 to trigger tier 1 exit.
    """
    entry_price = draw(st.floats(min_value=10.0, max_value=1000.0))
    risk_pct = draw(st.floats(min_value=0.01, max_value=0.10))
    stop_loss = entry_price * (1 - risk_pct)
    
    # R-multiple between 2.001 and 4.9 (before tier 2, with buffer for floating point)
    r_multiple = draw(st.floats(min_value=2.001, max_value=4.9))
    risk = entry_price - stop_loss
    current_price = entry_price + (r_multiple * risk)
    
    # Use reasonable quantities
    quantity = draw(st.floats(min_value=0.1, max_value=10.0))
    
    position = Position(
        symbol="TEST/USDT",
        side="long",
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=entry_price + (5.0 * risk),
        setup_type="momentum",
        posterior=0.70,
    )
    
    position.current_price = current_price
    position.highest_price = current_price
    
    return position


# ── Property Tests ──────────────────────────────────────────────────────

class TestTierExitExecution:
    """
    **Property 37: Tier exit execution**
    **Validates: Requirement 5.3**
    
    For any open position, when R-multiple reaches tier1_r_multiple (2.0),
    the system should execute partial exit of tier1_exit_pct (25%) of position.
    """
    
    @given(open_position_at_2r())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_tier1_exit_at_2r(self, position):
        """
        When a position reaches exactly 2R, tier 1 exit should be triggered.
        
        Property: For any position with R-multiple >= 2.0 and tiers_exited < 1,
        calling _check_tier_exits should:
        1. Execute a partial exit of 25% of the original quantity
        2. Update tiers_exited to 1
        3. Reduce remaining_quantity by the exit amount
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.tier1_r_multiple = 2.0
        settings.tier1_exit_pct = 0.25
        settings.tier2_r_multiple = 5.0
        settings.tier2_exit_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        # Add position to manager
        manager.positions[position.id] = position
        
        # Record initial state
        initial_quantity = position.quantity
        initial_remaining = position.remaining_quantity
        initial_tiers_exited = position.tiers_exited
        
        # Verify R-multiple is at or above 2.0 (with floating point tolerance)
        assert position.r_multiple >= 1.999, f"Position R-multiple should be >= 2.0, got {position.r_multiple}"
        assert initial_tiers_exited == 0, "Position should have no tiers exited initially"
        
        # Execute tier exit check
        await manager._check_tier_exits(position)
        
        # Verify tier 1 exit was executed
        expected_exit_qty = initial_quantity * 0.25
        expected_remaining = initial_remaining - expected_exit_qty
        
        # Property assertions
        assert position.tiers_exited == 1, \
            f"Tier 1 should be marked as exited, got tiers_exited={position.tiers_exited}"
        
        assert abs(position.remaining_quantity - expected_remaining) < 0.0001, \
            f"Remaining quantity should be {expected_remaining}, got {position.remaining_quantity}"
        
        # Verify trade was recorded
        tier1_trades = [t for t in position.trades if "tier1" in t.get("type", "")]
        assert len(tier1_trades) == 1, \
            f"Should have exactly 1 tier 1 exit trade, got {len(tier1_trades)}"
        
        tier1_trade = tier1_trades[0]
        assert abs(tier1_trade["quantity"] - expected_exit_qty) < 0.0001, \
            f"Exit quantity should be {expected_exit_qty}, got {tier1_trade['quantity']}"
        
        # Verify PnL was calculated
        assert "pnl" in tier1_trade, "Trade should have PnL recorded"
        expected_pnl = (position.current_price - position.entry_price) * expected_exit_qty
        assert abs(tier1_trade["pnl"] - expected_pnl) < 0.01, \
            f"PnL should be approximately {expected_pnl}, got {tier1_trade['pnl']}"
    
    @given(open_position_above_2r())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_tier1_exit_above_2r(self, position):
        """
        When a position exceeds 2R, tier 1 exit should still be triggered.
        
        Property: For any position with R-multiple >= 2.0 (even if > 2.0),
        tier 1 exit should execute 25% of position.
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.tier1_r_multiple = 2.0
        settings.tier1_exit_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        initial_quantity = position.quantity
        r_multiple = position.r_multiple
        
        # Verify R-multiple is above 2.0 (with floating point tolerance)
        assert r_multiple >= 1.999, f"R-multiple should be >= 2.0, got {r_multiple}"
        
        # Execute tier exit check
        await manager._check_tier_exits(position)
        
        # Verify tier 1 exit executed
        expected_exit_qty = initial_quantity * 0.25
        
        assert position.tiers_exited >= 1, \
            f"At least tier 1 should be exited for R={r_multiple}, got tiers_exited={position.tiers_exited}"
        
        # Find tier 1 trade
        tier1_trades = [t for t in position.trades if "tier1" in t.get("type", "")]
        assert len(tier1_trades) >= 1, \
            f"Should have at least 1 tier 1 exit trade for R={r_multiple}"
        
        # Verify the exit quantity is correct (25% of original)
        tier1_trade = tier1_trades[0]
        assert abs(tier1_trade["quantity"] - expected_exit_qty) < 0.0001, \
            f"Tier 1 exit should be 25% ({expected_exit_qty}), got {tier1_trade['quantity']}"
    
    @given(st.data())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_tier1_exit_only_once(self, data):
        """
        Tier 1 exit should only execute once, even if checked multiple times.
        
        Property: For any position that has already exited tier 1 (tiers_exited >= 1),
        calling _check_tier_exits again should NOT execute another tier 1 exit.
        """
        # Generate position at 2R
        position = data.draw(open_position_at_2r())
        
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.tier1_r_multiple = 2.0
        settings.tier1_exit_pct = 0.25
        settings.tier2_r_multiple = 5.0
        settings.tier2_exit_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        # Execute tier exit check first time
        await manager._check_tier_exits(position)
        
        # Record state after first exit
        remaining_after_first = position.remaining_quantity
        trades_after_first = len(position.trades)
        
        assert position.tiers_exited == 1, "Tier 1 should be exited after first check"
        
        # Execute tier exit check AGAIN (should not trigger another tier 1 exit)
        await manager._check_tier_exits(position)
        
        # Verify no additional tier 1 exit occurred
        assert position.remaining_quantity == remaining_after_first, \
            "Remaining quantity should not change on second check"
        
        tier1_trades = [t for t in position.trades if "tier1" in t.get("type", "")]
        assert len(tier1_trades) == 1, \
            f"Should still have exactly 1 tier 1 exit, got {len(tier1_trades)}"
    
    @given(open_position_at_2r())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_tier1_exit_percentage_accuracy(self, position):
        """
        Tier 1 exit should be exactly 25% of the original position quantity.
        
        Property: For any position at 2R, the tier 1 exit quantity should equal
        exactly tier1_exit_pct (0.25) multiplied by the original quantity.
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.tier1_r_multiple = 2.0
        settings.tier1_exit_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        original_quantity = position.quantity
        
        # Execute tier exit
        await manager._check_tier_exits(position)
        
        # Find tier 1 trade
        tier1_trades = [t for t in position.trades if "tier1" in t.get("type", "")]
        assert len(tier1_trades) == 1, "Should have exactly 1 tier 1 exit"
        
        tier1_trade = tier1_trades[0]
        exit_quantity = tier1_trade["quantity"]
        
        # Verify exit is exactly 25% of original
        expected_exit = original_quantity * 0.25
        
        # Allow small floating point tolerance
        assert abs(exit_quantity - expected_exit) < 0.0001, \
            f"Exit quantity should be exactly 25% of {original_quantity} = {expected_exit}, got {exit_quantity}"
        
        # Verify percentage
        exit_percentage = exit_quantity / original_quantity
        assert abs(exit_percentage - 0.25) < 0.0001, \
            f"Exit should be 25% of position, got {exit_percentage * 100:.2f}%"
