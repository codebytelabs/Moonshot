"""
Property-based tests for trailing stop activation and execution.

These tests use hypothesis to verify universal properties hold across
all valid inputs, complementing the example-based unit tests.
"""
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock
import time

from src.position_manager import Position, PositionManager, PositionState
from src.config import Settings


# ── Test Data Strategies ────────────────────────────────────────────────

@st.composite
def open_position_at_5r(draw):
    """
    Generate an open position that has reached 5R profit (tier 2 target).
    
    The position should have:
    - entry_price and stop_loss such that risk is defined
    - current_price such that R-multiple >= 5.0
    - remaining_quantity > 0 (some position still open)
    - tiers_exited < 2 (tier 2 not yet exited)
    """
    entry_price = draw(st.floats(min_value=10.0, max_value=1000.0))
    # Risk should be reasonable (1-10% of entry)
    risk_pct = draw(st.floats(min_value=0.01, max_value=0.10))
    stop_loss = entry_price * (1 - risk_pct)
    
    # Calculate current price for slightly above 5R to avoid floating point issues
    risk = entry_price - stop_loss
    # Add a tiny bit more to ensure we're definitely >= 5.0
    current_price = entry_price + (5.001 * risk)
    
    # Use reasonable quantities
    quantity = draw(st.floats(min_value=0.1, max_value=10.0))
    
    position = Position(
        symbol="TEST/USDT",
        side="long",
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=entry_price + (10.0 * risk),  # 10R target
        setup_type="breakout",
        posterior=0.75,
    )
    
    # Set current price to achieve 5R+
    position.current_price = current_price
    position.highest_price = current_price
    
    # Simulate that tier 1 has already been exited (25% sold)
    # This is realistic since we're at 5R
    position.tiers_exited = 1
    position.remaining_quantity = quantity * 0.75  # 75% remaining after tier 1
    
    return position


@st.composite
def open_position_above_5r(draw):
    """
    Generate an open position that has exceeded 5R profit.
    
    R-multiple should be >= 5.0 to trigger tier 2 exit and trailing stop activation.
    """
    entry_price = draw(st.floats(min_value=10.0, max_value=1000.0))
    risk_pct = draw(st.floats(min_value=0.01, max_value=0.10))
    stop_loss = entry_price * (1 - risk_pct)
    
    # R-multiple between 5.001 and 10.0
    r_multiple = draw(st.floats(min_value=5.001, max_value=10.0))
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
        take_profit=entry_price + (10.0 * risk),
        setup_type="momentum",
        posterior=0.70,
    )
    
    position.current_price = current_price
    position.highest_price = current_price
    
    # Simulate tier 1 already exited
    position.tiers_exited = 1
    position.remaining_quantity = quantity * 0.75
    
    return position


@st.composite
def trailing_stop_percentage(draw):
    """Generate a valid trailing stop percentage (15-40%)."""
    return draw(st.floats(min_value=0.15, max_value=0.40))


# ── Property Tests ──────────────────────────────────────────────────────

class TestTrailingStopActivation:
    """
    **Property 38: Trailing stop activation**
    **Validates: Requirement 5.4**
    
    For any open position, when R-multiple reaches tier2_r_multiple (5.0),
    trailing stop should be activated at current_price × (1 - trailing_stop_pct).
    """
    
    @given(open_position_at_5r(), trailing_stop_percentage())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_activates_at_5r(self, position, trailing_stop_pct):
        """
        When a position reaches exactly 5R, trailing stop should be activated.
        
        Property: For any position with R-multiple >= 5.0 and tiers_exited < 2,
        calling _check_tier_exits should:
        1. Execute tier 2 exit (25% of original position)
        2. Activate trailing stop (trailing_active = True)
        3. Set trailing_stop = current_price × (1 - trailing_stop_pct)
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
        settings.runner_trailing_stop_pct = trailing_stop_pct
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        # Add position to manager
        manager.positions[position.id] = position
        
        # Record initial state
        initial_trailing_active = position.trailing_active
        current_price = position.current_price
        r_multiple = position.r_multiple
        
        # Verify R-multiple is at or above 5.0 (with floating point tolerance)
        assert r_multiple >= 4.999, f"Position R-multiple should be >= 5.0, got {r_multiple}"
        assert initial_trailing_active is False, "Trailing stop should not be active initially"
        assert position.tiers_exited < 2, "Tier 2 should not be exited initially"
        
        # Execute tier exit check (this should trigger tier 2 and activate trailing stop)
        await manager._check_tier_exits(position)
        
        # Property assertions
        assert position.trailing_active is True, \
            f"Trailing stop should be activated at R={r_multiple}"
        
        # Calculate expected trailing stop price
        expected_trailing_stop = current_price * (1 - trailing_stop_pct)
        
        assert position.trailing_stop > 0, \
            "Trailing stop price should be set to a positive value"
        
        # Verify trailing stop is calculated correctly (with floating point tolerance)
        assert abs(position.trailing_stop - expected_trailing_stop) < 0.01, \
            f"Trailing stop should be {expected_trailing_stop:.6f}, got {position.trailing_stop:.6f}"
        
        # Verify trailing stop is below current price (makes sense for long position)
        assert position.trailing_stop < current_price, \
            f"Trailing stop ({position.trailing_stop:.6f}) should be below current price ({current_price:.6f})"
        
        # Verify tier 2 was also executed
        assert position.tiers_exited == 2, \
            f"Tier 2 should be marked as exited, got tiers_exited={position.tiers_exited}"
    
    @given(open_position_above_5r(), trailing_stop_percentage())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_activates_above_5r(self, position, trailing_stop_pct):
        """
        When a position exceeds 5R, trailing stop should still be activated.
        
        Property: For any position with R-multiple >= 5.0 (even if > 5.0),
        trailing stop should be activated at current_price × (1 - trailing_stop_pct).
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
        settings.runner_trailing_stop_pct = trailing_stop_pct
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        current_price = position.current_price
        r_multiple = position.r_multiple
        
        # Verify R-multiple is above 5.0
        assert r_multiple >= 4.999, f"R-multiple should be >= 5.0, got {r_multiple}"
        
        # Execute tier exit check
        await manager._check_tier_exits(position)
        
        # Verify trailing stop activated
        assert position.trailing_active is True, \
            f"Trailing stop should be activated at R={r_multiple}"
        
        expected_trailing_stop = current_price * (1 - trailing_stop_pct)
        
        assert abs(position.trailing_stop - expected_trailing_stop) < 0.01, \
            f"Trailing stop should be {expected_trailing_stop:.6f}, got {position.trailing_stop:.6f}"
    
    @given(open_position_at_5r())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_price_calculation(self, position):
        """
        Trailing stop price should be calculated as current_price × (1 - trailing_stop_pct).
        
        Property: For any position at 5R with trailing_stop_pct in [0.15, 0.40],
        the trailing stop price should equal current_price × (1 - trailing_stop_pct).
        """
        # Test with different trailing stop percentages
        trailing_stop_pct = 0.25  # 25% trailing stop
        
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
        settings.runner_trailing_stop_pct = trailing_stop_pct
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        current_price = position.current_price
        
        # Execute tier exit check
        await manager._check_tier_exits(position)
        
        # Calculate expected trailing stop
        expected_trailing_stop = current_price * (1 - trailing_stop_pct)
        
        # Verify calculation is correct
        assert abs(position.trailing_stop - expected_trailing_stop) < 0.01, \
            f"Trailing stop calculation incorrect: expected {expected_trailing_stop:.6f}, got {position.trailing_stop:.6f}"
        
        # Verify the percentage relationship
        actual_pct = (current_price - position.trailing_stop) / current_price
        assert abs(actual_pct - trailing_stop_pct) < 0.0001, \
            f"Trailing stop percentage should be {trailing_stop_pct * 100:.1f}%, got {actual_pct * 100:.1f}%"
    
    @given(open_position_at_5r(), trailing_stop_percentage())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_only_activates_once(self, position, trailing_stop_pct):
        """
        Trailing stop should only be activated once, even if checked multiple times.
        
        Property: For any position that has already activated trailing stop,
        calling _check_tier_exits again should NOT reset or change the trailing stop state.
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
        settings.runner_trailing_stop_pct = trailing_stop_pct
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        # Execute tier exit check first time
        await manager._check_tier_exits(position)
        
        # Record state after first activation
        first_trailing_active = position.trailing_active
        first_trailing_stop = position.trailing_stop
        first_tiers_exited = position.tiers_exited
        
        assert first_trailing_active is True, "Trailing stop should be active after first check"
        assert first_tiers_exited == 2, "Tier 2 should be exited after first check"
        
        # Execute tier exit check AGAIN (should not change trailing stop state)
        await manager._check_tier_exits(position)
        
        # Verify trailing stop state unchanged
        assert position.trailing_active == first_trailing_active, \
            "Trailing stop active state should not change on second check"
        
        assert position.trailing_stop == first_trailing_stop, \
            "Trailing stop price should not change on second check (unless price moved higher)"
        
        assert position.tiers_exited == first_tiers_exited, \
            "Tiers exited should not change on second check"
    
    @given(open_position_at_5r(), trailing_stop_percentage())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_requires_tier2_exit(self, position, trailing_stop_pct):
        """
        Trailing stop should only activate after tier 2 exit is executed.
        
        Property: For any position at 5R, trailing_active should only become True
        after tiers_exited is set to 2.
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
        settings.runner_trailing_stop_pct = trailing_stop_pct
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        # Verify initial state
        assert position.tiers_exited < 2, "Tier 2 should not be exited initially"
        assert position.trailing_active is False, "Trailing stop should not be active initially"
        
        # Execute tier exit check
        await manager._check_tier_exits(position)
        
        # Verify both tier 2 exit and trailing stop activation occurred together
        if position.trailing_active:
            assert position.tiers_exited == 2, \
                "If trailing stop is active, tier 2 must be exited"
        
        # At 5R, both should be true
        assert position.tiers_exited == 2, "Tier 2 should be exited at 5R"
        assert position.trailing_active is True, "Trailing stop should be active at 5R"


class TestTrailingStopExecution:
    """
    **Property 39: Trailing stop execution**
    **Validates: Requirement 5.5**
    
    For any position with active trailing stop, when current price drops to or below
    trailing_stop_price, remaining position should be closed.
    """
    
    @st.composite
    def position_with_active_trailing_stop_for_settings(draw, trailing_stop_pct=0.25):
        """
        Generate a position with an active trailing stop using a specific trailing stop percentage.
        
        The position should have:
        - trailing_active = True
        - trailing_stop calculated with the given trailing_stop_pct
        - remaining_quantity > 0
        - current_price initially above trailing_stop
        """
        entry_price = draw(st.floats(min_value=10.0, max_value=1000.0))
        risk_pct = draw(st.floats(min_value=0.01, max_value=0.10))
        stop_loss = entry_price * (1 - risk_pct)
        
        # Position has reached 5R+ and trailing stop is active
        risk = entry_price - stop_loss
        highest_price = entry_price + (draw(st.floats(min_value=5.5, max_value=10.0)) * risk)
        
        # Calculate trailing stop using the SAME percentage that will be used in settings
        trailing_stop = highest_price * (1 - trailing_stop_pct)
        
        # Current price is ALWAYS above trailing stop to ensure position is still open
        # Generate price between trailing_stop and highest_price
        current_price = draw(st.floats(
            min_value=trailing_stop * 1.05,  # At least 5% above trailing stop
            max_value=highest_price
        ))
        
        quantity = draw(st.floats(min_value=0.1, max_value=10.0))
        
        position = Position(
            symbol="TEST/USDT",
            side="long",
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=entry_price + (10.0 * risk),
            setup_type="momentum",
            posterior=0.70,
        )
        
        # Set position state to have active trailing stop
        position.current_price = current_price
        position.highest_price = highest_price
        position.trailing_active = True
        position.trailing_stop = trailing_stop
        
        # Simulate tiers already exited (tier 1 and tier 2)
        position.tiers_exited = 2
        position.remaining_quantity = quantity * 0.50  # 50% runner remaining
        
        return position
    
    @given(position_with_active_trailing_stop_for_settings(trailing_stop_pct=0.25))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_closes_position_when_hit(self, position):
        """
        When current price drops to or below trailing stop, position should be closed.
        
        Property: For any position with trailing_active=True and remaining_quantity>0,
        if current_price <= trailing_stop, then _check_trailing_stop should close
        the position with reason="trailing_stop".
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.runner_trailing_stop_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        # Record initial state
        initial_remaining_qty = position.remaining_quantity
        trailing_stop_price = position.trailing_stop
        
        # Verify preconditions
        assert position.trailing_active is True, "Trailing stop should be active"
        assert initial_remaining_qty > 0, "Position should have remaining quantity"
        assert position.status != PositionState.CLOSED, "Position should not be closed initially"
        
        # Simulate price dropping to trailing stop level
        position.current_price = trailing_stop_price
        
        # Execute trailing stop check
        await manager._check_trailing_stop(position)
        
        # Property assertions
        assert position.status == PositionState.CLOSED, \
            f"Position should be closed when price hits trailing stop"
        
        assert position.remaining_quantity == 0, \
            f"Remaining quantity should be 0 after trailing stop execution, got {position.remaining_quantity}"
        
        # Verify a trade was recorded with correct reason
        trailing_stop_trades = [t for t in position.trades if t.get("type") == "trailing_stop"]
        assert len(trailing_stop_trades) > 0, \
            "A trade with type='trailing_stop' should be recorded"
        
        # Verify the trade closed the full remaining quantity
        last_trade = position.trades[-1]
        assert last_trade["type"] == "trailing_stop", \
            f"Last trade should be trailing_stop, got {last_trade['type']}"
        
        assert abs(last_trade["quantity"] - initial_remaining_qty) < 0.0001, \
            f"Trade should close full remaining quantity ({initial_remaining_qty}), got {last_trade['quantity']}"
    
    @given(position_with_active_trailing_stop_for_settings(trailing_stop_pct=0.25))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_closes_when_price_below_stop(self, position):
        """
        When current price drops BELOW trailing stop, position should be closed.
        
        Property: For any position with trailing_active=True,
        if current_price < trailing_stop (not just equal), position should still be closed.
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.runner_trailing_stop_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        initial_remaining_qty = position.remaining_quantity
        trailing_stop_price = position.trailing_stop
        
        # Simulate price dropping BELOW trailing stop (by 1-5%)
        price_drop_pct = 0.01 + (0.04 * (hash(position.id) % 100) / 100)  # 1-5% below
        position.current_price = trailing_stop_price * (1 - price_drop_pct)
        
        # Verify price is below trailing stop
        assert position.current_price < trailing_stop_price, \
            f"Current price ({position.current_price}) should be below trailing stop ({trailing_stop_price})"
        
        # Execute trailing stop check
        await manager._check_trailing_stop(position)
        
        # Property assertions
        assert position.status == PositionState.CLOSED, \
            f"Position should be closed when price drops below trailing stop"
        
        assert position.remaining_quantity == 0, \
            f"Remaining quantity should be 0, got {position.remaining_quantity}"
        
        # Verify trade recorded
        trailing_stop_trades = [t for t in position.trades if t.get("type") == "trailing_stop"]
        assert len(trailing_stop_trades) > 0, \
            "A trailing_stop trade should be recorded"
    
    @given(position_with_active_trailing_stop_for_settings(trailing_stop_pct=0.25))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_does_not_close_when_above(self, position):
        """
        When current price is above trailing stop, position should remain open.
        
        Property: For any position with trailing_active=True,
        if current_price > trailing_stop, position should NOT be closed.
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.runner_trailing_stop_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        initial_remaining_qty = position.remaining_quantity
        initial_status = position.status
        trailing_stop_price = position.trailing_stop
        
        # Ensure price is WELL above trailing stop (by at least 5%)
        # Don't modify the price - the generator already ensures it's above
        # Just verify it
        assert position.current_price > trailing_stop_price, \
            f"Current price ({position.current_price}) should be above trailing stop ({trailing_stop_price})"
        
        # Execute trailing stop check
        await manager._check_trailing_stop(position)
        
        # Property assertions - position should NOT be closed
        assert position.status != PositionState.CLOSED, \
            f"Position should NOT be closed when price is above trailing stop"
        
        assert position.remaining_quantity == initial_remaining_qty, \
            f"Remaining quantity should be unchanged, was {initial_remaining_qty}, got {position.remaining_quantity}"
        
        # Verify no trailing_stop trade was recorded
        initial_trade_count = len(position.trades)
        trailing_stop_trades = [t for t in position.trades if t.get("type") == "trailing_stop"]
        assert len(trailing_stop_trades) == 0, \
            "No trailing_stop trade should be recorded when price is above stop"
    
    @given(position_with_active_trailing_stop_for_settings(trailing_stop_pct=0.25))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_updates_when_price_rises(self, position):
        """
        When price rises to new high, trailing stop should be updated upward.
        
        Property: For any position with trailing_active=True,
        if highest_price increases, trailing_stop should be updated to
        new_highest_price × (1 - trailing_stop_pct).
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        trailing_stop_pct = 0.25
        settings.runner_trailing_stop_pct = trailing_stop_pct
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        initial_trailing_stop = position.trailing_stop
        initial_highest_price = position.highest_price
        
        # Simulate price rising to new high (10% above current highest)
        # This ensures we definitely have a new high
        new_highest_price = initial_highest_price * 1.10
        position.current_price = new_highest_price
        position.highest_price = new_highest_price
        
        # Execute trailing stop check
        await manager._check_trailing_stop(position)
        
        # Calculate expected new trailing stop
        expected_trailing_stop = new_highest_price * (1 - trailing_stop_pct)
        
        # Property assertions
        assert position.trailing_stop > initial_trailing_stop, \
            f"Trailing stop should be updated upward when price rises to new high (was {initial_trailing_stop:.6f}, now {position.trailing_stop:.6f})"
        
        assert abs(position.trailing_stop - expected_trailing_stop) < 0.01, \
            f"Trailing stop should be {expected_trailing_stop:.6f}, got {position.trailing_stop:.6f}"
        
        # Position should still be open (price above trailing stop)
        assert position.status != PositionState.CLOSED, \
            "Position should remain open when price rises"
    
    @given(position_with_active_trailing_stop_for_settings(trailing_stop_pct=0.25))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_does_not_execute_when_inactive(self, position):
        """
        When trailing_active is False, trailing stop should not execute.
        
        Property: For any position with trailing_active=False,
        even if current_price <= trailing_stop, position should NOT be closed.
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.runner_trailing_stop_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        # Deactivate trailing stop
        position.trailing_active = False
        
        initial_remaining_qty = position.remaining_quantity
        trailing_stop_price = position.trailing_stop
        
        # Simulate price dropping below trailing stop
        position.current_price = trailing_stop_price * 0.95
        
        # Execute trailing stop check
        await manager._check_trailing_stop(position)
        
        # Property assertions - position should NOT be closed
        assert position.status != PositionState.CLOSED, \
            f"Position should NOT be closed when trailing_active is False"
        
        assert position.remaining_quantity == initial_remaining_qty, \
            f"Remaining quantity should be unchanged"
        
        # Verify no trailing_stop trade was recorded
        trailing_stop_trades = [t for t in position.trades if t.get("type") == "trailing_stop"]
        assert len(trailing_stop_trades) == 0, \
            "No trailing_stop trade should be recorded when trailing_active is False"
    
    @given(position_with_active_trailing_stop_for_settings(trailing_stop_pct=0.25))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_trailing_stop_closes_full_remaining_quantity(self, position):
        """
        When trailing stop executes, it should close the FULL remaining quantity.
        
        Property: For any position with trailing_active=True and remaining_quantity>0,
        when trailing stop executes, the trade quantity should equal remaining_quantity
        and remaining_quantity should become 0.
        """
        # Setup
        mock_exchange = MagicMock()
        mock_exchange.name = "test_exchange"
        mock_exchange.amount_to_precision = lambda symbol, qty: qty
        mock_exchange.create_market_sell = AsyncMock()
        
        settings = Settings()
        settings.runner_trailing_stop_pct = 0.25
        
        manager = PositionManager(
            exchange=mock_exchange,
            settings=settings,
            store=None,
            paper_mode=True
        )
        
        manager.positions[position.id] = position
        
        initial_remaining_qty = position.remaining_quantity
        
        # Verify precondition
        assert initial_remaining_qty > 0, "Position should have remaining quantity"
        
        # Simulate price dropping to trailing stop
        position.current_price = position.trailing_stop
        
        # Execute trailing stop check
        await manager._check_trailing_stop(position)
        
        # Property assertions
        assert position.remaining_quantity == 0, \
            f"Remaining quantity should be 0 after trailing stop, got {position.remaining_quantity}"
        
        # Verify the trade closed the full remaining quantity
        last_trade = position.trades[-1]
        assert last_trade["type"] == "trailing_stop", \
            f"Last trade should be trailing_stop"
        
        assert abs(last_trade["quantity"] - initial_remaining_qty) < 0.0001, \
            f"Trade quantity should equal initial remaining quantity ({initial_remaining_qty}), got {last_trade['quantity']}"
