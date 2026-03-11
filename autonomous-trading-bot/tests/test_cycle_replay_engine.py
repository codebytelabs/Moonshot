"""
Unit tests for CycleReplayEngine.
Tests slippage calculation, fee calculation, order fill logic, and cycle simulation.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from src.cycle_replay_engine import (
    CycleReplayEngine,
    BacktestConfig,
    Order,
    OrderType,
    OrderSide,
    Position,
    BacktestResult
)


class TestSlippageCalculation:
    """Test slippage calculation based on ATR and volume impact."""
    
    def test_low_volatility_buy_slippage(self):
        """Test slippage for low volatility buy order."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        price = 100.0
        atr_pct = 1.5  # < 2%
        volume_impact = 0.003  # < 0.5%
        
        slipped_price = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        # Should apply 0.05% slippage upward for buy
        expected = price * 1.0005
        assert abs(slipped_price - expected) < 0.01
    
    def test_medium_volatility_sell_slippage(self):
        """Test slippage for medium volatility sell order."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        price = 50000.0
        atr_pct = 3.5  # 2-5%
        volume_impact = 0.007  # 0.5-1%
        
        slipped_price = engine.calculate_slippage(price, OrderSide.SELL, atr_pct, volume_impact)
        
        # Should apply 0.10% + 0.05% = 0.15% slippage downward for sell
        expected = price * 0.9985
        assert abs(slipped_price - expected) < 1.0
    
    def test_high_volatility_large_order_slippage(self):
        """Test slippage for high volatility with large order size."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        price = 2000.0
        atr_pct = 6.0  # > 5%
        volume_impact = 0.015  # > 1%
        
        slipped_price = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        # Should apply 0.15% + 0.10% = 0.25% slippage upward
        expected = price * 1.0025
        assert abs(slipped_price - expected) < 0.5
    
    def test_zero_volume_impact(self):
        """Test slippage with no volume impact."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        price = 1000.0
        atr_pct = 2.5
        volume_impact = 0.0
        
        slipped_price = engine.calculate_slippage(price, OrderSide.BUY, atr_pct, volume_impact)
        
        # Should only apply base slippage (0.10%)
        expected = price * 1.001
        assert abs(slipped_price - expected) < 0.2


class TestFeeCalculation:
    """Test trading fee calculation."""
    
    def test_maker_fee(self):
        """Test maker fee calculation for limit orders."""
        config = BacktestConfig(maker_fee_pct=0.1)
        engine = CycleReplayEngine(data_loader=Mock(), config=config)
        
        notional = 10000.0
        fee = engine.calculate_fees(notional, OrderType.LIMIT)
        
        # 0.1% of 10000 = 10
        assert fee == 10.0
    
    def test_taker_fee(self):
        """Test taker fee calculation for market orders."""
        config = BacktestConfig(taker_fee_pct=0.1)
        engine = CycleReplayEngine(data_loader=Mock(), config=config)
        
        notional = 5000.0
        fee = engine.calculate_fees(notional, OrderType.MARKET)
        
        # 0.1% of 5000 = 5
        assert fee == 5.0
    
    def test_different_fee_rates(self):
        """Test with different maker/taker fee rates."""
        config = BacktestConfig(maker_fee_pct=0.05, taker_fee_pct=0.15)
        engine = CycleReplayEngine(data_loader=Mock(), config=config)
        
        notional = 20000.0
        
        maker_fee = engine.calculate_fees(notional, OrderType.LIMIT)
        taker_fee = engine.calculate_fees(notional, OrderType.MARKET)
        
        assert maker_fee == 10.0  # 0.05% of 20000
        assert taker_fee == 30.0  # 0.15% of 20000


class TestLimitOrderFill:
    """Test limit order fill logic."""
    
    def test_buy_limit_fills_when_price_touches(self):
        """Test buy limit order fills when candle low touches limit price."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        order = Order(
            order_id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=50000.0
        )
        
        candle = {
            'open': 50500.0,
            'high': 51000.0,
            'low': 49900.0,  # Touches below limit
            'close': 50300.0,
            'volume': 100.0
        }
        
        should_fill = engine.check_limit_order_fill(order, candle)
        assert should_fill is True
    
    def test_buy_limit_does_not_fill_above_price(self):
        """Test buy limit order doesn't fill when price stays above."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        order = Order(
            order_id="test_2",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=50000.0
        )
        
        candle = {
            'open': 50500.0,
            'high': 51000.0,
            'low': 50100.0,  # Stays above limit
            'close': 50300.0,
            'volume': 100.0
        }
        
        should_fill = engine.check_limit_order_fill(order, candle)
        assert should_fill is False
    
    def test_sell_limit_fills_when_price_touches(self):
        """Test sell limit order fills when candle high touches limit price."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        order = Order(
            order_id="test_3",
            symbol="ETH/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=10.0,
            price=3000.0
        )
        
        candle = {
            'open': 2950.0,
            'high': 3010.0,  # Touches above limit
            'low': 2900.0,
            'close': 2980.0,
            'volume': 500.0
        }
        
        should_fill = engine.check_limit_order_fill(order, candle)
        assert should_fill is True
    
    def test_sell_limit_does_not_fill_below_price(self):
        """Test sell limit order doesn't fill when price stays below."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        order = Order(
            order_id="test_4",
            symbol="ETH/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=10.0,
            price=3000.0
        )
        
        candle = {
            'open': 2950.0,
            'high': 2990.0,  # Stays below limit
            'low': 2900.0,
            'close': 2980.0,
            'volume': 500.0
        }
        
        should_fill = engine.check_limit_order_fill(order, candle)
        assert should_fill is False
    
    def test_market_order_always_returns_false(self):
        """Test that market orders don't use limit fill logic."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        order = Order(
            order_id="test_5",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        
        candle = {
            'open': 50000.0,
            'high': 51000.0,
            'low': 49000.0,
            'close': 50500.0,
            'volume': 100.0
        }
        
        should_fill = engine.check_limit_order_fill(order, candle)
        assert should_fill is False


class TestPositionManagement:
    """Test position tracking and management."""
    
    def test_position_unrealized_pnl(self):
        """Test unrealized PnL calculation."""
        position = Position(
            position_id="pos_1",
            symbol="BTC/USDT",
            side="long",
            entry_price=50000.0,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=48000.0,
            take_profit=55000.0,
            setup_type="breakout",
            posterior=0.75,
            entry_timestamp=datetime.now(),
            current_price=52000.0
        )
        
        # PnL = (52000 - 50000) * 1.0 = 2000
        assert position.unrealized_pnl == 2000.0
    
    def test_position_r_multiple(self):
        """Test R-multiple calculation."""
        position = Position(
            position_id="pos_2",
            symbol="ETH/USDT",
            side="long",
            entry_price=3000.0,
            quantity=10.0,
            remaining_quantity=10.0,
            stop_loss=2900.0,  # Risk = 100
            take_profit=3500.0,
            setup_type="momentum",
            posterior=0.70,
            entry_timestamp=datetime.now(),
            current_price=3200.0  # Profit = 200
        )
        
        # R-multiple = 200 / 100 = 2.0R
        assert position.r_multiple == 2.0
    
    def test_position_r_multiple_with_loss(self):
        """Test R-multiple calculation with losing position."""
        position = Position(
            position_id="pos_3",
            symbol="SOL/USDT",
            side="long",
            entry_price=100.0,
            quantity=50.0,
            remaining_quantity=50.0,
            stop_loss=95.0,  # Risk = 5
            take_profit=110.0,
            setup_type="pullback",
            posterior=0.68,
            entry_timestamp=datetime.now(),
            current_price=97.0  # Loss = -3
        )
        
        # R-multiple = -3 / 5 = -0.6R
        assert position.r_multiple == -0.6


class TestBacktestResult:
    """Test backtest result calculations."""
    
    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        trades = [
            {'pnl': 100},
            {'pnl': -50},
            {'pnl': 200},
            {'pnl': -30},
            {'pnl': 150}
        ]
        
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000.0,
            final_equity=105000.0,
            total_trades=5,
            winning_trades=3,
            losing_trades=2,
            total_pnl=370.0,
            equity_curve=Mock(),
            trades=trades,
            config=BacktestConfig()
        )
        
        # Win rate = 3/5 = 0.6 = 60%
        assert result.win_rate == 0.6
    
    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        trades = [
            {'pnl': 500},
            {'pnl': -200},
            {'pnl': 300},
            {'pnl': -100}
        ]
        
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000.0,
            final_equity=100500.0,
            total_trades=4,
            winning_trades=2,
            losing_trades=2,
            total_pnl=500.0,
            equity_curve=Mock(),
            trades=trades,
            config=BacktestConfig()
        )
        
        # Profit factor = 800 / 300 = 2.67
        assert abs(result.profit_factor - 2.67) < 0.01
    
    def test_profit_factor_with_no_losses(self):
        """Test profit factor when there are no losing trades."""
        trades = [
            {'pnl': 500},
            {'pnl': 300},
            {'pnl': 200}
        ]
        
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000.0,
            final_equity=101000.0,
            total_trades=3,
            winning_trades=3,
            losing_trades=0,
            total_pnl=1000.0,
            equity_curve=Mock(),
            trades=trades,
            config=BacktestConfig()
        )
        
        # Profit factor should be infinity
        assert result.profit_factor == float('inf')


@pytest.mark.asyncio
class TestCycleSimulation:
    """Test cycle simulation logic."""
    
    async def test_update_positions_with_market_data(self):
        """Test that positions are updated with current market prices."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        
        # Create a position
        position = Position(
            position_id="pos_1",
            symbol="BTC/USDT",
            side="long",
            entry_price=50000.0,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=48000.0,
            take_profit=55000.0,
            setup_type="breakout",
            posterior=0.75,
            entry_timestamp=datetime.now(),
            current_price=50000.0,
            highest_price=50000.0
        )
        
        engine.positions["pos_1"] = position
        
        # Market data with new prices
        market_data = {
            "BTC/USDT": {
                "5m": {
                    "open": 50500.0,
                    "high": 51500.0,
                    "low": 50200.0,
                    "close": 51000.0,
                    "volume": 100.0
                }
            }
        }
        
        engine._update_positions(market_data)
        
        # Position should be updated
        assert position.current_price == 51000.0
        assert position.highest_price == 51500.0
    
    async def test_stop_loss_triggers_position_close(self):
        """Test that hitting stop loss closes the position."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        engine.cash = 100000.0
        
        # Create a position
        position = Position(
            position_id="pos_1",
            symbol="BTC/USDT",
            side="long",
            entry_price=50000.0,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=48000.0,
            take_profit=55000.0,
            setup_type="breakout",
            posterior=0.75,
            entry_timestamp=datetime.now(),
            current_price=50000.0,
            highest_price=50000.0
        )
        
        engine.positions["pos_1"] = position
        
        # Market data with price hitting stop loss
        market_data = {
            "BTC/USDT": {
                "5m": {
                    "open": 49000.0,
                    "high": 49500.0,
                    "low": 47500.0,  # Hits stop loss
                    "close": 48500.0,
                    "volume": 200.0
                }
            }
        }
        
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Position should be closed
        assert len(closed_trades) == 1
        assert closed_trades[0]['exit_reason'] == 'stop_loss'
        assert "pos_1" not in engine.positions
    
    async def test_tier1_exit_at_2r(self):
        """Test that tier 1 exit triggers at 2R."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        engine.cash = 100000.0
        
        # Create a position
        position = Position(
            position_id="pos_1",
            symbol="BTC/USDT",
            side="long",
            entry_price=50000.0,
            quantity=1.0,
            remaining_quantity=1.0,
            stop_loss=48000.0,  # Risk = 2000
            take_profit=55000.0,
            setup_type="breakout",
            posterior=0.75,
            entry_timestamp=datetime.now(),
            current_price=50000.0,
            highest_price=50000.0,
            tiers_exited=0
        )
        
        engine.positions["pos_1"] = position
        
        # Market data with price at 2R (50000 + 2*2000 = 54000)
        market_data = {
            "BTC/USDT": {
                "5m": {
                    "open": 53500.0,
                    "high": 54500.0,
                    "low": 53000.0,
                    "close": 54000.0,
                    "volume": 150.0
                }
            }
        }
        
        # Update position price first
        engine._update_positions(market_data)
        
        closed_trades = engine._check_exits(market_data, datetime.now())
        
        # Should have tier 1 exit
        assert len(closed_trades) == 1
        assert closed_trades[0]['exit_reason'] == 'tier1_2R'
        assert position.tiers_exited == 1
        assert position.remaining_quantity == 0.75  # 75% remaining


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error handling."""
    
    async def test_zero_risk_position_rejected(self):
        """Test that positions with zero or negative risk are rejected."""
        engine = CycleReplayEngine(data_loader=Mock(), config=BacktestConfig())
        engine.cash = 100000.0
        
        signals = [{
            'symbol': 'BTC/USDT',
            'entry_price': 50000.0,
            'stop_loss': 50000.0,  # Same as entry = zero risk
            'take_profit': 55000.0,
            'posterior': 0.75,
            'setup_type': 'breakout',
            'atr_pct': 2.0
        }]
        
        market_data = {
            "BTC/USDT": {
                "5m": {
                    "open": 50000.0,
                    "high": 50500.0,
                    "low": 49500.0,
                    "close": 50000.0,
                    "volume": 100.0
                }
            }
        }
        
        new_positions = engine._process_signals(signals, market_data, datetime.now())
        
        # Should not create position
        assert len(new_positions) == 0
    
    async def test_insufficient_cash_rejects_signal(self):
        """Test that signals are rejected when insufficient cash."""
        config = BacktestConfig(initial_capital=100.0, position_size_pct=0.5)  # 50% risk
        engine = CycleReplayEngine(data_loader=Mock(), config=config)
        engine.cash = 100.0  # Very low cash
        
        signals = [{
            'symbol': 'BTC/USDT',
            'entry_price': 50000.0,
            'stop_loss': 48000.0,  # Risk = 2000 per unit
            'take_profit': 55000.0,
            'posterior': 0.75,
            'setup_type': 'breakout',
            'atr_pct': 2.0
        }]
        
        market_data = {
            "BTC/USDT": {
                "5m": {
                    "open": 50000.0,
                    "high": 50500.0,
                    "low": 49500.0,
                    "close": 50000.0,
                    "volume": 100.0
                }
            }
        }
        
        new_positions = engine._process_signals(signals, market_data, datetime.now())
        
        # Should not create position due to insufficient cash
        # Risk amount = 100 * 0.5 = 50, quantity = 50/2000 = 0.025
        # Notional = 50000 * 0.025 = 1250, which exceeds cash of 100
        assert len(new_positions) == 0
    
    async def test_max_positions_limit(self):
        """Test that max positions limit is enforced."""
        config = BacktestConfig(max_positions=2)
        engine = CycleReplayEngine(data_loader=Mock(), config=config)
        engine.cash = 100000.0
        
        # Add 2 existing positions
        for i in range(2):
            position = Position(
                position_id=f"pos_{i}",
                symbol=f"BTC/USDT",
                side="long",
                entry_price=50000.0,
                quantity=1.0,
                remaining_quantity=1.0,
                stop_loss=48000.0,
                take_profit=55000.0,
                setup_type="breakout",
                posterior=0.75,
                entry_timestamp=datetime.now(),
                current_price=50000.0
            )
            engine.positions[f"pos_{i}"] = position
        
        # Try to add another signal
        signals = [{
            'symbol': 'ETH/USDT',
            'entry_price': 3000.0,
            'stop_loss': 2900.0,
            'take_profit': 3300.0,
            'posterior': 0.75,
            'setup_type': 'momentum',
            'atr_pct': 2.0
        }]
        
        market_data = {}
        new_positions = engine._process_signals(signals, market_data, datetime.now())
        
        # Should not create new position
        assert len(new_positions) == 0
        assert len(engine.positions) == 2
