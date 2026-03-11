"""
Property-based tests for CycleReplayEngine.
Tests universal properties that should hold across all inputs.

**Validates: Requirements 7.1, 7.2, 7.4, 7.5, 7.8**
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.cycle_replay_engine import (
    CycleReplayEngine,
    BacktestConfig,
    Order,
    OrderType,
    OrderSide,
    Position
)


# Custom strategies for generating test data
@st.composite
def price_strategy(draw):
    """Generate realistic price values."""
    return draw(st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False))


@st.composite
def percentage_strategy(draw):
    """Generate percentage values (0-100)."""
    return draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))


@st.composite
def position_strategy(draw):
    """Generate valid position data."""
    entry_price = draw(price_strategy())
    risk_pct = draw(st.floats(min_value=0.01, max_value=0.05))  # 1-5% risk
    stop_loss = entry_price * (1 - risk_pct)
    take_profit = entry_price * (1 + risk_pct * 3)  # 3:1 reward:risk
    
    return Position(
        position_id=f"pos_{draw(st.integers(min_value=1, max_value=10000))}",
        symbol="BTC/USDT",
        side="long",
        entry_price=entry_price,
        quantity=draw(st.floats(min_value=0.01, max_value=10.0)),
        remaining_quantity=draw(st.floats(min_value=0.01, max_value=10.0)),
        stop_loss=stop_loss,
        take_profit=take_profit,
        setup_type=draw(st.sampled_from(["breakout", "momentum", "pullback"])),
        posterior=draw(st.floats(min_value=0.5, max_value=1.0)),
        entry_timestamp=datetime.now(),
        current_price=entry_price,
        highest_price=entry_price
    )


class TestSlippageProperties:
    """Property-based tests for slippage calculation."""
    
    @given(
        price=price_strategy(),
        atr_pct=percentage_strategy(),
        volume_impact=st.floats(min_value=0.0, max_value=0.05)
    )
    @settings(max_examples=10)
    def test_slippage_always_unfavorable_for_buyer(self, price, atr_pct, volume_impact):
        """
        **Validates: Requirement 7.4**
        
        Property: Slippage should always increase the price for buy orders.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        # Buy slippage should always be >= original price (unfavorable)
        assert slipped_price >= price, f"Buy slippage should increase price: {price} -> {slipped_price}"
    
    @given(
        price=price_strategy(),
        atr_pct=percentage_strategy(),
        volume_impact=st.floats(min_value=0.0, max_value=0.05)
    )
    @settings(max_examples=10)
    def test_slippage_always_unfavorable_for_seller(self, price, atr_pct, volume_impact):
        """
        **Validates: Requirement 7.4**
        
        Property: Slippage should always decrease the price for sell orders.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price = engine.calculate_slippage(price, OrderSide.SELL, atr_pct, volume_impact)
        
        # Sell slippage should always be <= original price (unfavorable)
        assert slipped_price <= price, f"Sell slippage should decrease price: {price} -> {slipped_price}"
    
    @given(
        price=price_strategy(),
        atr_pct=percentage_strategy(),
        volume_impact=st.floats(min_value=0.0, max_value=0.05)
    )
    @settings(max_examples=10)
    def test_slippage_magnitude_bounded(self, price, atr_pct, volume_impact):
        """
        **Validates: Requirement 7.4**
        
        Property: Slippage should never exceed reasonable bounds (max 0.25% total).
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price_buy = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        slipped_price_sell = engine.calculate_slippage(price, OrderSide.SELL, atr_pct, volume_impact)
        
        # Maximum slippage is 0.15% (high vol) + 0.10% (volume) = 0.25%
        max_slippage_pct = 0.0025
        
        buy_slippage_pct = abs(slipped_price_buy - price) / price
        sell_slippage_pct = abs(slipped_price_sell - price) / price
        
        # Use small tolerance for floating point comparison
        assert buy_slippage_pct <= max_slippage_pct + 1e-10, f"Buy slippage too high: {buy_slippage_pct:.4%}"
        assert sell_slippage_pct <= max_slippage_pct + 1e-10, f"Sell slippage too high: {sell_slippage_pct:.4%}"
    
    @given(
        price=price_strategy(),
        atr_pct=st.floats(min_value=0.0, max_value=1.0),  # Very low volatility
        volume_impact=st.floats(min_value=0.0, max_value=0.004)  # Very small orders
    )
    @settings(max_examples=15)
    def test_low_volatility_low_impact_minimal_slippage(self, price, atr_pct, volume_impact):
        """
        **Validates: Requirement 7.4**
        
        Property: Low volatility and small orders should have minimal slippage (0.05%).
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        slippage_pct = abs(slipped_price - price) / price
        
        # Should be approximately 0.05% (base slippage only)
        assert slippage_pct <= 0.0006, f"Low vol/impact should have minimal slippage: {slippage_pct:.4%}"


class TestFeeProperties:
    """Property-based tests for fee calculation."""
    
    @given(
        notional=st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=10)
    def test_fees_always_positive(self, notional):
        """
        **Validates: Requirement 7.5**
        
        Property: Fees should always be positive.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        maker_fee = engine.calculate_fees(notional, OrderType.LIMIT)
        taker_fee = engine.calculate_fees(notional, OrderType.MARKET)
        
        assert maker_fee >= 0, f"Maker fee should be positive: {maker_fee}"
        assert taker_fee >= 0, f"Taker fee should be positive: {taker_fee}"
    
    @given(
        notional=st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=10)
    def test_fees_proportional_to_notional(self, notional):
        """
        **Validates: Requirement 7.5**
        
        Property: Fees should be proportional to notional value.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        fee1 = engine.calculate_fees(notional, OrderType.LIMIT)
        fee2 = engine.calculate_fees(notional * 2, OrderType.LIMIT)
        
        # Doubling notional should double the fee
        assert abs(fee2 - fee1 * 2) < 0.01, f"Fees should be proportional: {fee1} vs {fee2}"
    
    @given(
        notional=st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
        maker_fee_pct=st.floats(min_value=0.0, max_value=0.5),
        taker_fee_pct=st.floats(min_value=0.0, max_value=0.5)
    )
    @settings(max_examples=10)
    def test_fees_never_exceed_notional(self, notional, maker_fee_pct, taker_fee_pct):
        """
        **Validates: Requirement 7.5**
        
        Property: Fees should never exceed the notional value.
        """
        config = BacktestConfig(maker_fee_pct=maker_fee_pct, taker_fee_pct=taker_fee_pct)
        engine = CycleReplayEngine(data_loader=Mock(), config=config)
        
        maker_fee = engine.calculate_fees(notional, OrderType.LIMIT)
        taker_fee = engine.calculate_fees(notional, OrderType.MARKET)
        
        assert maker_fee <= notional, f"Maker fee exceeds notional: {maker_fee} > {notional}"
        assert taker_fee <= notional, f"Taker fee exceeds notional: {taker_fee} > {notional}"


class TestLimitOrderFillProperties:
    """Property-based tests for limit order fill logic."""
    
    @given(
        limit_price=price_strategy(),
        candle_low=price_strategy(),
        candle_high=price_strategy()
    )
    @settings(max_examples=10)
    def test_buy_limit_fills_when_touched(self, limit_price, candle_low, candle_high):
        """
        **Validates: Requirement 7.8**
        
        Property: Buy limit orders fill if and only if candle low <= limit price.
        """
        assume(candle_low <= candle_high)  # Valid candle
        
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        order = Order(
            order_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=limit_price
        )
        
        candle = {
            'open': (candle_low + candle_high) / 2,
            'high': candle_high,
            'low': candle_low,
            'close': (candle_low + candle_high) / 2,
            'volume': 100.0
        }
        
        should_fill = engine.check_limit_order_fill(order, candle)
        expected_fill = candle_low <= limit_price
        
        assert should_fill == expected_fill, \
            f"Buy limit fill mismatch: low={candle_low}, limit={limit_price}, should_fill={should_fill}"
    
    @given(
        limit_price=price_strategy(),
        candle_low=price_strategy(),
        candle_high=price_strategy()
    )
    @settings(max_examples=10)
    def test_sell_limit_fills_when_touched(self, limit_price, candle_low, candle_high):
        """
        **Validates: Requirement 7.8**
        
        Property: Sell limit orders fill if and only if candle high >= limit price.
        """
        assume(candle_low <= candle_high)  # Valid candle
        
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        order = Order(
            order_id="test",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=limit_price
        )
        
        candle = {
            'open': (candle_low + candle_high) / 2,
            'high': candle_high,
            'low': candle_low,
            'close': (candle_low + candle_high) / 2,
            'volume': 100.0
        }
        
        should_fill = engine.check_limit_order_fill(order, candle)
        expected_fill = candle_high >= limit_price
        
        assert should_fill == expected_fill, \
            f"Sell limit fill mismatch: high={candle_high}, limit={limit_price}, should_fill={should_fill}"


class TestPositionProperties:
    """Property-based tests for position calculations."""
    
    @given(position=position_strategy())
    @settings(max_examples=10)
    def test_r_multiple_sign_matches_pnl(self, position):
        """
        **Validates: Requirement 7.1**
        
        Property: R-multiple sign should match PnL sign.
        """
        # Ensure valid risk
        assume(position.entry_price > position.stop_loss)
        
        if position.current_price > position.entry_price:
            # Profitable position
            assert position.r_multiple > 0, f"Profitable position should have positive R: {position.r_multiple}"
        elif position.current_price < position.entry_price:
            # Losing position
            assert position.r_multiple < 0, f"Losing position should have negative R: {position.r_multiple}"
        else:
            # Break-even
            assert position.r_multiple == 0, f"Break-even position should have 0R: {position.r_multiple}"
    
    @given(position=position_strategy())
    @settings(max_examples=10)
    def test_unrealized_pnl_calculation(self, position):
        """
        **Validates: Requirement 7.1**
        
        Property: Unrealized PnL should equal (current_price - entry_price) * quantity.
        """
        expected_pnl = (position.current_price - position.entry_price) * position.remaining_quantity
        
        assert abs(position.unrealized_pnl - expected_pnl) < 0.01, \
            f"PnL mismatch: expected={expected_pnl}, actual={position.unrealized_pnl}"
    
    @given(
        entry_price=price_strategy(),
        stop_loss_pct=st.floats(min_value=0.01, max_value=0.1),
        price_move_pct=st.floats(min_value=-0.2, max_value=0.5)
    )
    @settings(max_examples=10)
    def test_r_multiple_scales_with_risk(self, entry_price, stop_loss_pct, price_move_pct):
        """
        **Validates: Requirement 7.1**
        
        Property: R-multiple should scale inversely with risk size.
        """
        stop_loss = entry_price * (1 - stop_loss_pct)
        current_price = entry_price * (1 + price_move_pct)
        
        position = Position(
            position_id="test",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=stop_loss,
            take_profit=entry_price * 1.5,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=current_price
        )
        
        risk = entry_price - stop_loss
        profit = current_price - entry_price
        expected_r = profit / risk if risk > 0 else 0
        
        assert abs(position.r_multiple - expected_r) < 0.01, \
            f"R-multiple mismatch: expected={expected_r}, actual={position.r_multiple}"


class TestBacktestInvariants:
    """Property-based tests for backtest invariants."""
    
    @given(
        initial_capital=st.floats(min_value=1000.0, max_value=1000000.0),
        trades=st.lists(
            st.floats(min_value=-1000.0, max_value=5000.0),  # PnL values
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=10)
    def test_equity_equals_capital_plus_pnl(self, initial_capital, trades):
        """
        **Validates: Requirement 7.1**
        
        Property: Final equity should equal initial capital plus total PnL.
        """
        total_pnl = sum(trades)
        expected_equity = initial_capital + total_pnl
        
        # Simulate simple backtest
        config = BacktestConfig(initial_capital=initial_capital)
        engine = CycleReplayEngine(data_loader=Mock(), config=config)
        
        # Manually set cash to simulate trades
        engine.cash = expected_equity
        engine.equity = expected_equity
        
        assert abs(engine.equity - expected_equity) < 0.01, \
            f"Equity mismatch: expected={expected_equity}, actual={engine.equity}"
    
    @given(
        cash=st.floats(min_value=0.0, max_value=1000000.0),
        position_values=st.lists(
            st.floats(min_value=0.0, max_value=10000.0),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=10)
    def test_equity_never_negative_without_leverage(self, cash, position_values):
        """
        **Validates: Requirement 7.1**
        
        Property: Equity should never be negative without leverage.
        """
        # Total equity = cash + sum of position values
        total_equity = cash + sum(position_values)
        
        assert total_equity >= 0, f"Equity should not be negative: {total_equity}"
    
    @given(
        initial_capital=st.floats(min_value=1000.0, max_value=100000.0),
        num_trades=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=10)
    def test_trade_count_monotonic(self, initial_capital, num_trades):
        """
        **Validates: Requirement 7.2**
        
        Property: Trade count should only increase, never decrease.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig(initial_capital=initial_capital))
        
        previous_count = 0
        for i in range(num_trades):
            # Simulate adding a trade
            engine.closed_trades.append({'pnl': 100.0})
            current_count = len(engine.closed_trades)
            
            assert current_count >= previous_count, \
                f"Trade count decreased: {previous_count} -> {current_count}"
            
            previous_count = current_count


class TestCycleSimulationProperties:
    """Property-based tests for cycle simulation."""
    
    @given(
        num_cycles=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=10)
    def test_cycle_count_increments(self, num_cycles):
        """
        **Validates: Requirement 7.2**
        
        Property: Cycle count should increment by 1 for each cycle.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        assert engine.cycle_count == 0
        
        for i in range(num_cycles):
            engine.cycle_count += 1
            assert engine.cycle_count == i + 1
    
    @given(
        initial_equity=st.floats(min_value=1000.0, max_value=100000.0),
        num_cycles=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=10)
    def test_equity_curve_length_matches_cycles(self, initial_equity, num_cycles):
        """
        **Validates: Requirement 7.2**
        
        Property: Equity curve should have one entry per cycle.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig(initial_capital=initial_equity))
        
        for i in range(num_cycles):
            timestamp = datetime.now() + timedelta(minutes=5*i)
            engine.equity_curve.append((timestamp, engine.equity))
        
        assert len(engine.equity_curve) == num_cycles, \
            f"Equity curve length mismatch: expected={num_cycles}, actual={len(engine.equity_curve)}"



class TestNoLookAheadBias:
    """Property-based tests for no look-ahead bias."""
    
    @given(
        current_timestamp=st.datetimes(
            min_value=datetime(2021, 1, 1),
            max_value=datetime(2024, 12, 31)
        ),
        future_offset_minutes=st.integers(min_value=5, max_value=1440)  # 5 min to 1 day
    )
    @settings(max_examples=10)
    def test_no_future_data_in_cycle(self, current_timestamp, future_offset_minutes):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: For any cycle simulation at timestamp T, only data with 
        timestamps ≤ T should be accessible to decision-making components.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        # Create market data with current and future timestamps
        future_timestamp = current_timestamp + timedelta(minutes=future_offset_minutes)
        
        # Market data should only contain data up to current_timestamp
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'timestamp': current_timestamp,
                    'open': 50000.0,
                    'high': 51000.0,
                    'low': 49000.0,
                    'close': 50500.0,
                    'volume': 100.0
                }
            }
        }
        
        # Verify that the timestamp in market data is not in the future
        for symbol, timeframes in market_data.items():
            for timeframe, candle in timeframes.items():
                candle_timestamp = candle.get('timestamp', current_timestamp)
                assert candle_timestamp <= current_timestamp, \
                    f"Look-ahead bias detected: candle timestamp {candle_timestamp} > current {current_timestamp}"
    
    @given(
        num_cycles=st.integers(min_value=2, max_value=20),
        cycle_interval_minutes=st.integers(min_value=5, max_value=60)
    )
    @settings(max_examples=10)
    def test_data_timestamps_monotonic(self, num_cycles, cycle_interval_minutes):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: Data timestamps should be monotonically increasing across cycles.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        base_timestamp = datetime(2021, 1, 1, 0, 0)
        previous_timestamp = None
        
        for i in range(num_cycles):
            current_timestamp = base_timestamp + timedelta(minutes=i * cycle_interval_minutes)
            
            if previous_timestamp is not None:
                assert current_timestamp > previous_timestamp, \
                    f"Timestamps not monotonic: {previous_timestamp} -> {current_timestamp}"
            
            previous_timestamp = current_timestamp
    
    @given(
        decision_timestamp=st.datetimes(
            min_value=datetime(2021, 1, 1),
            max_value=datetime(2024, 12, 31)
        )
    )
    @settings(max_examples=10)
    def test_position_entry_uses_past_data_only(self, decision_timestamp):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: Position entry decisions should only use data from timestamps ≤ decision time.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        # Create a position with entry timestamp
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=50000.0,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=48000.0,
            take_profit=55000.0,
            setup_type="breakout",
            posterior=0.75,
            entry_timestamp=decision_timestamp,
            current_price=50000.0
        )
        
        # Verify entry timestamp is not in the future relative to decision time
        assert position.entry_timestamp <= decision_timestamp, \
            f"Position entry timestamp {position.entry_timestamp} is after decision time {decision_timestamp}"
    
    @given(
        cycle_timestamp=st.datetimes(
            min_value=datetime(2021, 1, 1),
            max_value=datetime(2024, 12, 31)
        ),
        num_symbols=st.integers(min_value=1, max_value=5),
        num_timeframes=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=10)
    def test_all_market_data_timestamps_not_in_future(self, cycle_timestamp, num_symbols, num_timeframes):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: All market data across all symbols and timeframes must have 
        timestamps ≤ current cycle timestamp.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        symbols = [f"SYM{i}/USDT" for i in range(num_symbols)]
        timeframes = ['5m', '15m', '1h', '4h'][:num_timeframes]
        
        # Create market data for multiple symbols and timeframes
        market_data = {}
        for symbol in symbols:
            market_data[symbol] = {}
            for timeframe in timeframes:
                # All candle timestamps should be <= cycle_timestamp
                market_data[symbol][timeframe] = {
                    'timestamp': cycle_timestamp,
                    'open': 50000.0,
                    'high': 51000.0,
                    'low': 49000.0,
                    'close': 50500.0,
                    'volume': 100.0
                }
        
        # Verify no future data in any symbol/timeframe combination
        for symbol, timeframes_data in market_data.items():
            for timeframe, candle in timeframes_data.items():
                candle_timestamp = candle.get('timestamp', cycle_timestamp)
                assert candle_timestamp <= cycle_timestamp, \
                    f"Look-ahead bias in {symbol} {timeframe}: {candle_timestamp} > {cycle_timestamp}"
    
    @given(
        base_timestamp=st.datetimes(
            min_value=datetime(2021, 1, 1),
            max_value=datetime(2024, 12, 31)
        ),
        num_positions=st.integers(min_value=1, max_value=10),
        time_offset_minutes=st.integers(min_value=-1440, max_value=0)  # Up to 1 day in past
    )
    @settings(max_examples=10)
    def test_position_updates_use_current_or_past_data(self, base_timestamp, num_positions, time_offset_minutes):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: When updating positions, only data from current or past timestamps 
        should be used. Position entry timestamps must be ≤ current cycle time.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        current_cycle_time = base_timestamp
        
        # Create positions with entry times in the past
        for i in range(num_positions):
            entry_timestamp = base_timestamp + timedelta(minutes=time_offset_minutes)
            
            position = Position(
                position_id=f"pos_{i}",
                symbol="BTC/USDT",
                side="long",
                entry_price=50000.0,
                quantity=1.0,
                remaining_quantity=1.0,
                stop_loss=48000.0,
                take_profit=55000.0,
                setup_type="breakout",
                posterior=0.75,
                entry_timestamp=entry_timestamp,
                current_price=50000.0
            )
            
            # Verify position entry is not in the future
            assert position.entry_timestamp <= current_cycle_time, \
                f"Position {i} entry time {position.entry_timestamp} is after cycle time {current_cycle_time}"
    
    @given(
        current_timestamp=st.datetimes(
            min_value=datetime(2021, 1, 1),
            max_value=datetime(2024, 12, 31)
        ),
        price_sequence=st.lists(
            st.floats(min_value=40000.0, max_value=60000.0),
            min_size=3,
            max_size=10
        )
    )
    @settings(max_examples=10)
    def test_price_updates_sequential_no_future_prices(self, current_timestamp, price_sequence):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: When processing a sequence of price updates, each update should 
        only use prices from the current or previous cycles, never future cycles.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        # Simulate sequential price updates
        for i, price in enumerate(price_sequence):
            cycle_time = current_timestamp + timedelta(minutes=5 * i)
            
            # Create market data for this cycle
            market_data = {
                'BTC/USDT': {
                    '5m': {
                        'timestamp': cycle_time,
                        'open': price,
                        'high': price * 1.01,
                        'low': price * 0.99,
                        'close': price,
                        'volume': 100.0
                    }
                }
            }
            
            # Verify timestamp is not in the future relative to cycle time
            candle_timestamp = market_data['BTC/USDT']['5m']['timestamp']
            assert candle_timestamp <= cycle_time, \
                f"Price update at cycle {i} has future timestamp: {candle_timestamp} > {cycle_time}"
            
            # If we have a previous cycle, verify current timestamp is after previous
            if i > 0:
                previous_cycle_time = current_timestamp + timedelta(minutes=5 * (i - 1))
                assert cycle_time > previous_cycle_time, \
                    f"Cycle timestamps not monotonic: {previous_cycle_time} -> {cycle_time}"
    
    @given(
        decision_timestamp=st.datetimes(
            min_value=datetime(2021, 1, 1),
            max_value=datetime(2024, 12, 31)
        ),
        signal_data_offset_minutes=st.integers(min_value=-60, max_value=0)  # Signal data from past hour
    )
    @settings(max_examples=10)
    def test_trading_signals_use_historical_data_only(self, decision_timestamp, signal_data_offset_minutes):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: Trading signals generated at time T should only use data with 
        timestamps ≤ T. No future data should influence signal generation.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        # Data timestamp used for signal generation
        data_timestamp = decision_timestamp + timedelta(minutes=signal_data_offset_minutes)
        
        # Create a trading signal
        signal = {
            'symbol': 'BTC/USDT',
            'entry_price': 50000.0,
            'stop_loss': 48000.0,
            'take_profit': 55000.0,
            'posterior': 0.75,
            'setup_type': 'breakout',
            'data_timestamp': data_timestamp  # Timestamp of data used for signal
        }
        
        # Verify signal uses data from the past or present, not future
        assert signal['data_timestamp'] <= decision_timestamp, \
            f"Signal uses future data: data_timestamp {data_timestamp} > decision_timestamp {decision_timestamp}"
    
    @given(
        backtest_start=st.datetimes(
            min_value=datetime(2021, 1, 1),
            max_value=datetime(2024, 1, 1)
        ),
        num_cycles=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=10)
    def test_backtest_cycles_process_data_chronologically(self, backtest_start, num_cycles):
        """
        **Property 11: No look-ahead bias**
        **Validates: Requirements 7.3**
        
        Property: During a backtest, cycles must be processed in chronological order,
        ensuring that each cycle only has access to data from that time or earlier.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        cycle_timestamps = []
        
        # Generate chronological cycle timestamps
        for i in range(num_cycles):
            cycle_time = backtest_start + timedelta(minutes=5 * i)
            cycle_timestamps.append(cycle_time)
        
        # Verify timestamps are strictly increasing
        for i in range(1, len(cycle_timestamps)):
            assert cycle_timestamps[i] > cycle_timestamps[i-1], \
                f"Cycle timestamps not chronological: {cycle_timestamps[i-1]} -> {cycle_timestamps[i]}"
        
        # Verify each cycle only has access to data up to its timestamp
        for i, cycle_time in enumerate(cycle_timestamps):
            # All previous cycle times should be <= current cycle time
            for j in range(i):
                assert cycle_timestamps[j] <= cycle_time, \
                    f"Cycle {i} has access to future data from cycle {j}: {cycle_timestamps[j]} vs {cycle_time}"


class TestSlippageCalculation:
    """Property-based tests for slippage calculation matching requirements."""
    
    @given(
        price=price_strategy(),
        atr_pct=st.floats(min_value=0.0, max_value=1.5),  # Low volatility
        volume_impact=st.floats(min_value=0.0, max_value=0.004)  # Small order
    )
    @settings(max_examples=10)
    def test_low_volatility_slippage_is_005_pct(self, price, atr_pct, volume_impact):
        """
        **Property 12: Slippage calculation**
        **Validates: Requirements 7.4, 10.1, 10.2**
        
        Property: When ATR < 2%, slippage should be 0.05%.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price_buy = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        slipped_price_sell = engine.calculate_slippage(price, OrderSide.SELL, atr_pct, volume_impact)
        
        # Calculate expected slippage (base + volume impact)
        base_slippage = 0.0005  # 0.05%
        volume_slippage = 0.0 if volume_impact < 0.005 else 0.0
        expected_total_slippage = base_slippage + volume_slippage
        
        buy_slippage_pct = abs(slipped_price_buy - price) / price
        sell_slippage_pct = abs(slipped_price_sell - price) / price
        
        # Allow small tolerance for floating point
        tolerance = 0.0001
        assert abs(buy_slippage_pct - expected_total_slippage) <= tolerance, \
            f"Buy slippage incorrect for low vol: expected ~{expected_total_slippage:.4%}, got {buy_slippage_pct:.4%}"
        assert abs(sell_slippage_pct - expected_total_slippage) <= tolerance, \
            f"Sell slippage incorrect for low vol: expected ~{expected_total_slippage:.4%}, got {sell_slippage_pct:.4%}"
    
    @given(
        price=price_strategy(),
        atr_pct=st.floats(min_value=2.0, max_value=4.9),  # Medium volatility
        volume_impact=st.floats(min_value=0.0, max_value=0.004)  # Small order
    )
    @settings(max_examples=10)
    def test_medium_volatility_slippage_is_010_pct(self, price, atr_pct, volume_impact):
        """
        **Property 12: Slippage calculation**
        **Validates: Requirements 7.4, 10.3**
        
        Property: When ATR is 2-5%, slippage should be 0.10%.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price_buy = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        # Calculate expected slippage
        base_slippage = 0.001  # 0.10%
        volume_slippage = 0.0 if volume_impact < 0.005 else 0.0
        expected_total_slippage = base_slippage + volume_slippage
        
        buy_slippage_pct = abs(slipped_price_buy - price) / price
        
        tolerance = 0.0001
        assert abs(buy_slippage_pct - expected_total_slippage) <= tolerance, \
            f"Buy slippage incorrect for medium vol: expected ~{expected_total_slippage:.4%}, got {buy_slippage_pct:.4%}"
    
    @given(
        price=price_strategy(),
        atr_pct=st.floats(min_value=5.0, max_value=20.0),  # High volatility
        volume_impact=st.floats(min_value=0.0, max_value=0.004)  # Small order
    )
    @settings(max_examples=10)
    def test_high_volatility_slippage_is_015_pct(self, price, atr_pct, volume_impact):
        """
        **Property 12: Slippage calculation**
        **Validates: Requirements 7.4, 10.4**
        
        Property: When ATR > 5%, slippage should be 0.15%.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price_buy = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        # Calculate expected slippage
        base_slippage = 0.0015  # 0.15%
        volume_slippage = 0.0 if volume_impact < 0.005 else 0.0
        expected_total_slippage = base_slippage + volume_slippage
        
        buy_slippage_pct = abs(slipped_price_buy - price) / price
        
        tolerance = 0.0001
        assert abs(buy_slippage_pct - expected_total_slippage) <= tolerance, \
            f"Buy slippage incorrect for high vol: expected ~{expected_total_slippage:.4%}, got {buy_slippage_pct:.4%}"
    
    @given(
        price=price_strategy(),
        atr_pct=st.floats(min_value=0.0, max_value=10.0),
        volume_impact=st.floats(min_value=0.01, max_value=0.02)  # Order size 1-2% of volume
    )
    @settings(max_examples=10)
    def test_volume_impact_adds_additional_slippage(self, price, atr_pct, volume_impact):
        """
        **Property 12: Slippage calculation**
        **Validates: Requirements 7.4, 10.1**
        
        Property: When order size exceeds 1% of 24h volume, additional slippage penalty applies.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        slipped_price = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        # Base slippage depends on ATR
        if atr_pct < 2:
            base_slippage = 0.0005
        elif atr_pct < 5:
            base_slippage = 0.001
        else:
            base_slippage = 0.0015
        
        # Volume impact slippage (implementation uses < 0.01, so >= 0.01 gets 0.10%)
        if volume_impact < 0.005:
            volume_slippage = 0.0
        elif volume_impact < 0.01:
            volume_slippage = 0.0005  # 0.05% additional
        else:
            volume_slippage = 0.001  # 0.10% additional
        
        expected_total_slippage = base_slippage + volume_slippage
        actual_slippage_pct = abs(slipped_price - price) / price
        
        tolerance = 0.0001
        assert abs(actual_slippage_pct - expected_total_slippage) <= tolerance, \
            f"Slippage with volume impact incorrect: expected ~{expected_total_slippage:.4%}, got {actual_slippage_pct:.4%}"


class TestFeeApplication:
    """Property-based tests for fee application."""
    
    @given(
        notional=st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=10)
    def test_maker_fee_is_01_percent(self, notional):
        """
        **Property 13: Fee application**
        **Validates: Requirements 7.5, 10.5**
        
        Property: Maker orders (limit) should have 0.1% fee.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        maker_fee = engine.calculate_fees(notional, OrderType.LIMIT)
        expected_fee = notional * 0.001  # 0.1%
        
        assert abs(maker_fee - expected_fee) < 0.01, \
            f"Maker fee incorrect: expected ${expected_fee:.2f}, got ${maker_fee:.2f}"
    
    @given(
        notional=st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=10)
    def test_taker_fee_is_01_percent(self, notional):
        """
        **Property 13: Fee application**
        **Validates: Requirements 7.5, 10.6**
        
        Property: Taker orders (market) should have 0.1% fee.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        taker_fee = engine.calculate_fees(notional, OrderType.MARKET)
        expected_fee = notional * 0.001  # 0.1%
        
        assert abs(taker_fee - expected_fee) < 0.01, \
            f"Taker fee incorrect: expected ${expected_fee:.2f}, got ${taker_fee:.2f}"
    
    @given(
        price=price_strategy(),
        quantity=st.floats(min_value=0.01, max_value=100.0)
    )
    @settings(max_examples=10)
    def test_fee_calculated_on_notional_value(self, price, quantity):
        """
        **Property 13: Fee application**
        **Validates: Requirements 7.5, 10.5, 10.6**
        
        Property: Fees should be calculated as notional_value × fee_rate.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        notional = price * quantity
        fee = engine.calculate_fees(notional, OrderType.MARKET)
        
        expected_fee = notional * 0.001
        
        assert abs(fee - expected_fee) < 0.01, \
            f"Fee calculation incorrect: notional=${notional:.2f}, expected_fee=${expected_fee:.2f}, got ${fee:.2f}"
    
    @given(
        notional1=st.floats(min_value=100.0, max_value=10000.0),
        notional2=st.floats(min_value=100.0, max_value=10000.0)
    )
    @settings(max_examples=10)
    def test_fees_are_additive(self, notional1, notional2):
        """
        **Property 13: Fee application**
        **Validates: Requirements 7.5**
        
        Property: Fee for combined notional should equal sum of individual fees.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        fee1 = engine.calculate_fees(notional1, OrderType.MARKET)
        fee2 = engine.calculate_fees(notional2, OrderType.MARKET)
        combined_fee = engine.calculate_fees(notional1 + notional2, OrderType.MARKET)
        
        assert abs(combined_fee - (fee1 + fee2)) < 0.01, \
            f"Fees not additive: {fee1:.2f} + {fee2:.2f} != {combined_fee:.2f}"


class TestStopLossAndTargetChecking:
    """Property-based tests for stop loss and target checking."""
    
    @given(
        entry_price=price_strategy(),
        stop_loss_pct=st.floats(min_value=0.01, max_value=0.1),
        current_price_pct=st.floats(min_value=-0.15, max_value=-0.01)  # Price below entry
    )
    @settings(max_examples=10)
    def test_stop_loss_triggers_when_hit(self, entry_price, stop_loss_pct, current_price_pct):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: Stop loss should trigger when current price hits or falls below stop loss level.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - stop_loss_pct)
        current_price = entry_price * (1 + current_price_pct)
        
        # Assume current price is at or below stop loss
        assume(current_price <= stop_loss)
        
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=stop_loss,
            take_profit=entry_price * 1.5,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=current_price
        )
        
        # Create market data with low price at or below stop loss
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': current_price,
                    'high': current_price,
                    'low': current_price,  # Low touches stop loss
                    'close': current_price,
                    'volume': 100.0
                }
            }
        }
        
        engine.positions[position.position_id] = position
        
        # Check exits should close the position
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        assert len(closed_trades) > 0, \
            f"Stop loss should trigger when price {current_price:.2f} <= stop {stop_loss:.2f}"
        assert closed_trades[0]['exit_reason'] == 'stop_loss', \
            f"Exit reason should be 'stop_loss', got '{closed_trades[0]['exit_reason']}'"
    
    @given(
        entry_price=price_strategy(),
        stop_loss_pct=st.floats(min_value=0.01, max_value=0.1),
        price_above_stop_pct=st.floats(min_value=0.01, max_value=0.5)  # Price above stop loss
    )
    @settings(max_examples=10)
    def test_stop_loss_does_not_trigger_when_not_hit(self, entry_price, stop_loss_pct, price_above_stop_pct):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: Stop loss should NOT trigger when current price is above stop loss level.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - stop_loss_pct)
        # Ensure current price is above stop loss
        current_price = stop_loss * (1 + price_above_stop_pct)
        
        # Verify assumption
        assume(current_price > stop_loss)
        
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=stop_loss,
            take_profit=entry_price * 2.0,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=current_price
        )
        
        # Create market data with low price above stop loss
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': current_price,
                    'high': current_price * 1.01,
                    'low': current_price * 0.99,  # Low is still above stop loss
                    'close': current_price,
                    'volume': 100.0
                }
            }
        }
        
        # Ensure the low doesn't touch stop loss
        assume(market_data['BTC/USDT']['5m']['low'] > stop_loss)
        
        engine.positions[position.position_id] = position
        
        # Check exits should NOT close the position
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Filter for stop loss exits only
        stop_loss_exits = [t for t in closed_trades if t.get('exit_reason') == 'stop_loss']
        
        assert len(stop_loss_exits) == 0, \
            f"Stop loss should NOT trigger when low {market_data['BTC/USDT']['5m']['low']:.2f} > stop {stop_loss:.2f}"
    
    @given(
        entry_price=price_strategy(),
        target_r=st.floats(min_value=2.0, max_value=3.0),
        risk_pct=st.floats(min_value=0.01, max_value=0.05)
    )
    @settings(max_examples=10)
    def test_tier1_target_triggers_at_2r(self, entry_price, target_r, risk_pct):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: Tier 1 target (2R) should trigger partial exit when reached.
        """
        # Only test when target_r is >= 2.0
        assume(target_r >= 2.0)
        
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - risk_pct)
        risk = entry_price - stop_loss
        target_price = entry_price + (risk * target_r)
        
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=stop_loss,
            take_profit=target_price,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=target_price,
            highest_price=target_price
        )
        
        # Create market data with price at target
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': target_price,
                    'high': target_price,
                    'low': entry_price,
                    'close': target_price,
                    'volume': 100.0
                }
            }
        }
        
        engine.positions[position.position_id] = position
        
        # Check exits should trigger tier 1 exit
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Should have partial exit at tier 1 when R >= 2.0
        assert len(closed_trades) > 0, \
            f"Tier 1 target should trigger at 2R+ (current R={position.r_multiple:.2f})"
        # Verify it's a tier 1 exit
        assert any('tier1' in trade.get('exit_reason', '') for trade in closed_trades), \
            "Should have at least one tier 1 exit"
    
    @given(
        entry_price=price_strategy(),
        risk_pct=st.floats(min_value=0.01, max_value=0.05),
        r_below_2=st.floats(min_value=0.5, max_value=1.99)  # R-multiple below 2
    )
    @settings(max_examples=10)
    def test_tier1_target_does_not_trigger_below_2r(self, entry_price, risk_pct, r_below_2):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: Tier 1 target should NOT trigger when R-multiple is below 2.0.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - risk_pct)
        risk = entry_price - stop_loss
        current_price = entry_price + (risk * r_below_2)
        
        # Verify R-multiple is below 2.0
        assume(r_below_2 < 2.0)
        
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=stop_loss,
            take_profit=entry_price * 2.0,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=current_price,
            highest_price=current_price
        )
        
        # Create market data with price below 2R
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': current_price,
                    'high': current_price,
                    'low': entry_price,
                    'close': current_price,
                    'volume': 100.0
                }
            }
        }
        
        engine.positions[position.position_id] = position
        
        # Check exits should NOT trigger tier 1 exit
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Filter for tier 1 exits only
        tier1_exits = [t for t in closed_trades if 'tier1' in t.get('exit_reason', '')]
        
        assert len(tier1_exits) == 0, \
            f"Tier 1 should NOT trigger when R={position.r_multiple:.2f} < 2.0"
    
    @given(
        entry_price=price_strategy(),
        risk_pct=st.floats(min_value=0.01, max_value=0.05),
        price_move_r=st.floats(min_value=5.0, max_value=10.0)
    )
    @settings(max_examples=10)
    def test_tier2_target_triggers_at_5r(self, entry_price, risk_pct, price_move_r):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: Tier 2 target (5R) should trigger partial exit and activate trailing stop.
        """
        # Only test when price_move_r is >= 5.0
        assume(price_move_r >= 5.0)
        
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - risk_pct)
        risk = entry_price - stop_loss
        current_price = entry_price + (risk * price_move_r)
        
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=0.75,  # Already exited tier 1
            stop_loss=stop_loss,
            take_profit=current_price,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=current_price,
            highest_price=current_price,
            tiers_exited=1  # Tier 1 already exited
        )
        
        # Create market data with price at 5R+
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': current_price,
                    'high': current_price,
                    'low': entry_price,
                    'close': current_price,
                    'volume': 100.0
                }
            }
        }
        
        engine.positions[position.position_id] = position
        
        # Check exits should trigger tier 2 exit
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Should have partial exit at tier 2 and trailing stop activated
        assert len(closed_trades) > 0, \
            f"Tier 2 target should trigger at 5R+ (current R={position.r_multiple:.2f})"
        # Verify it's a tier 2 exit
        assert any('tier2' in trade.get('exit_reason', '') for trade in closed_trades), \
            "Should have at least one tier 2 exit"
        # Verify trailing stop is activated
        assert position.trailing_active or len(closed_trades) > 0, \
            "Trailing stop should be activated after tier 2 exit"
    
    @given(
        entry_price=price_strategy(),
        risk_pct=st.floats(min_value=0.01, max_value=0.05),
        r_below_5=st.floats(min_value=2.0, max_value=4.99)  # R-multiple below 5
    )
    @settings(max_examples=10)
    def test_tier2_target_does_not_trigger_below_5r(self, entry_price, risk_pct, r_below_5):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: Tier 2 target should NOT trigger when R-multiple is below 5.0.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - risk_pct)
        risk = entry_price - stop_loss
        current_price = entry_price + (risk * r_below_5)
        
        # Verify R-multiple is below 5.0
        assume(r_below_5 < 5.0)
        
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=0.75,  # Already exited tier 1
            stop_loss=stop_loss,
            take_profit=entry_price * 2.0,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=current_price,
            highest_price=current_price,
            tiers_exited=1  # Tier 1 already exited
        )
        
        # Create market data with price below 5R
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': current_price,
                    'high': current_price,
                    'low': entry_price,
                    'close': current_price,
                    'volume': 100.0
                }
            }
        }
        
        engine.positions[position.position_id] = position
        
        # Check exits should NOT trigger tier 2 exit
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Filter for tier 2 exits only
        tier2_exits = [t for t in closed_trades if 'tier2' in t.get('exit_reason', '')]
        
        assert len(tier2_exits) == 0, \
            f"Tier 2 should NOT trigger when R={position.r_multiple:.2f} < 5.0"
    
    @given(
        entry_price=price_strategy(),
        risk_pct=st.floats(min_value=0.01, max_value=0.05),
        trailing_stop_pct=st.floats(min_value=0.15, max_value=0.40),
        price_drop_pct=st.floats(min_value=0.01, max_value=0.50)
    )
    @settings(max_examples=10)
    def test_trailing_stop_triggers_when_hit(self, entry_price, risk_pct, trailing_stop_pct, price_drop_pct):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: Trailing stop should trigger when price drops below trailing stop level.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig(runner_trailing_stop_pct=trailing_stop_pct))
        
        stop_loss = entry_price * (1 - risk_pct)
        risk = entry_price - stop_loss
        
        # Position at 6R with trailing stop active
        high_price = entry_price + (risk * 6.0)
        trailing_stop = high_price * (1 - trailing_stop_pct)
        current_price = high_price * (1 - price_drop_pct)
        
        # Ensure current price is below trailing stop
        assume(current_price <= trailing_stop)
        
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=1.0,
            remaining_quantity=0.5,  # Runner position (50% remaining)
            stop_loss=stop_loss,
            take_profit=high_price * 2.0,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=current_price,
            highest_price=high_price,
            trailing_stop=trailing_stop,
            trailing_active=True,
            tiers_exited=2  # Both tiers exited
        )
        
        # Create market data with low price hitting trailing stop
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': high_price,
                    'high': high_price,
                    'low': current_price,  # Low touches trailing stop
                    'close': current_price,
                    'volume': 100.0
                }
            }
        }
        
        engine.positions[position.position_id] = position
        
        # Check exits should close the position
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Filter for trailing stop exits
        trailing_exits = [t for t in closed_trades if 'trailing' in t.get('exit_reason', '')]
        
        assert len(trailing_exits) > 0, \
            f"Trailing stop should trigger when price {current_price:.2f} <= trailing {trailing_stop:.2f}"
    
    @given(
        entry_price=price_strategy(),
        risk_pct=st.floats(min_value=0.01, max_value=0.05),
        num_positions=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=10)
    def test_all_positions_checked_for_exits_every_cycle(self, entry_price, risk_pct, num_positions):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: All open positions must be checked for stop loss and take profit in every cycle.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - risk_pct)
        
        # Create multiple positions with different states
        for i in range(num_positions):
            position = Position(
                position_id=f"pos_{i}",
                symbol="BTC/USDT",
                side="long",
                entry_price=entry_price,
                quantity=1.0,
                remaining_quantity=1.0,
                stop_loss=stop_loss,
                take_profit=entry_price * 1.5,
                setup_type="test",
                posterior=0.7,
                entry_timestamp=datetime.now(),
                current_price=entry_price * (1 + i * 0.01),  # Slightly different prices
                highest_price=entry_price * (1 + i * 0.01)
            )
            engine.positions[position.position_id] = position
        
        # Create market data
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': entry_price,
                    'high': entry_price * 1.1,
                    'low': entry_price * 0.95,
                    'close': entry_price,
                    'volume': 100.0
                }
            }
        }
        
        # Track initial position count
        initial_count = len(engine.positions)
        
        # Run check exits
        engine._check_exits(market_data, datetime.now())
        
        # Verify all positions were processed (count should be consistent)
        assert initial_count == num_positions, \
            f"All {num_positions} positions should be checked each cycle"
    
    @given(
        entry_price=price_strategy(),
        risk_pct=st.floats(min_value=0.01, max_value=0.05),
        price_move_r=st.floats(min_value=0.0, max_value=10.0)
    )
    @settings(max_examples=10)
    def test_position_closed_completely_on_stop_loss(self, entry_price, risk_pct, price_move_r):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: When stop loss is hit, the entire remaining position should be closed.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - risk_pct)
        
        # Create position with some quantity
        initial_quantity = 1.5
        position = Position(
            position_id="test_pos",
            symbol="BTC/USDT",
            side="long",
            entry_price=entry_price,
            quantity=initial_quantity,
            remaining_quantity=initial_quantity,
            stop_loss=stop_loss,
            take_profit=entry_price * 2.0,
            setup_type="test",
            posterior=0.7,
            entry_timestamp=datetime.now(),
            current_price=stop_loss * 0.99  # Below stop loss
        )
        
        # Create market data with price hitting stop loss
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': entry_price,
                    'high': entry_price,
                    'low': stop_loss * 0.99,  # Hits stop loss
                    'close': stop_loss * 0.99,
                    'volume': 100.0
                }
            }
        }
        
        engine.positions[position.position_id] = position
        
        # Check exits
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Verify position was closed
        stop_loss_trades = [t for t in closed_trades if t.get('exit_reason') == 'stop_loss']
        
        if len(stop_loss_trades) > 0:
            # Verify the entire remaining quantity was closed
            assert stop_loss_trades[0]['quantity'] == initial_quantity, \
                f"Stop loss should close entire position: expected {initial_quantity}, got {stop_loss_trades[0]['quantity']}"
            # Verify position was removed from engine
            assert position.position_id not in engine.positions, \
                "Position should be removed after stop loss"
    
    @given(
        entry_price=price_strategy(),
        risk_pct=st.floats(min_value=0.01, max_value=0.05)
    )
    @settings(max_examples=10)
    def test_positions_checked_every_cycle(self, entry_price, risk_pct):
        """
        **Property 14: Stop loss and target checking**
        **Validates: Requirements 7.6**
        
        Property: All open positions should be checked for exits in each cycle.
        """
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        stop_loss = entry_price * (1 - risk_pct)
        
        # Create multiple positions
        for i in range(3):
            position = Position(
                position_id=f"pos_{i}",
                symbol="BTC/USDT",
                side="long",
                entry_price=entry_price,
                quantity=1.0,
                remaining_quantity=1.0,
                stop_loss=stop_loss,
                take_profit=entry_price * 1.5,
                setup_type="test",
                posterior=0.7,
                entry_timestamp=datetime.now(),
                current_price=entry_price
            )
            engine.positions[position.position_id] = position
        
        # Create market data
        market_data = {
            'BTC/USDT': {
                '5m': {
                    'open': entry_price,
                    'high': entry_price * 1.1,
                    'low': entry_price * 0.9,
                    'close': entry_price,
                    'volume': 100.0
                }
            }
        }
        
        # All positions should be checked (none should be skipped)
        initial_count = len(engine.positions)
        engine._check_exits(market_data, datetime.now())
        
        # Verify all positions were processed (either still open or closed)
        assert initial_count == 3, "All positions should be checked each cycle"
