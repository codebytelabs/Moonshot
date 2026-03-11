"""
Cycle Replay Engine for Backtesting Framework.
Simulates 5-minute trading cycles with realistic slippage, fees, and order execution.

**Validates: Requirements 7.1, 7.2, 7.4, 7.5, 7.8**
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

import pandas as pd
import numpy as np


class OrderType(Enum):
    """Order types for backtesting."""
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """Represents a trading order in the backtest."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None  # For limit orders
    timestamp: datetime = field(default_factory=datetime.now)
    filled: bool = False
    fill_price: Optional[float] = None
    fill_timestamp: Optional[datetime] = None
    slippage: float = 0.0
    fees: float = 0.0


@dataclass
class Position:
    """Represents an open position in the backtest."""
    position_id: str
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    quantity: float
    remaining_quantity: float
    stop_loss: float
    take_profit: float
    setup_type: str
    posterior: float
    entry_timestamp: datetime
    current_price: float = 0.0
    highest_price: float = 0.0
    trailing_stop: float = 0.0
    trailing_active: bool = False
    tiers_exited: int = 0
    trades: List[Dict] = field(default_factory=list)
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL."""
        return (self.current_price - self.entry_price) * self.remaining_quantity
    
    @property
    def r_multiple(self) -> float:
        """Calculate R-multiple (risk units)."""
        risk = self.entry_price - self.stop_loss
        if risk <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / risk


@dataclass
class BacktestConfig:
    """Configuration for backtest execution."""
    initial_capital: float = 100000.0
    position_size_pct: float = 0.02  # 2% risk per trade
    maker_fee_pct: float = 0.1  # 0.1% maker fee
    taker_fee_pct: float = 0.1  # 0.1% taker fee
    slippage_base_pct: float = 0.05  # Base slippage 0.05%
    tier1_target_r: float = 2.0  # First tier exit at 2R
    tier2_target_r: float = 5.0  # Second tier exit at 5R
    tier1_exit_pct: float = 0.25  # Exit 25% at tier 1
    tier2_exit_pct: float = 0.25  # Exit 25% at tier 2
    runner_trailing_stop_pct: float = 0.25  # 25% trailing stop for runner
    bayesian_threshold: float = 0.65  # Decision threshold
    max_positions: int = 5  # Maximum concurrent positions


@dataclass
class CycleResult:
    """Result from simulating a single cycle."""
    timestamp: datetime
    positions_opened: int = 0
    positions_closed: int = 0
    orders_filled: int = 0
    equity: float = 0.0
    cash: float = 0.0
    trades: List[Dict] = field(default_factory=list)


@dataclass
class BacktestResult:
    """Complete backtest results."""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_equity: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    equity_curve: pd.Series
    trades: List[Dict]
    config: BacktestConfig
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    @property
    def profit_factor(self) -> float:
        """Calculate profit factor."""
        gross_profits = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        gross_losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        if gross_losses == 0:
            return float('inf') if gross_profits > 0 else 0.0
        return gross_profits / gross_losses


class CycleReplayEngine:
    """
    Simulates 5-minute trading cycles for backtesting.
    
    Features:
    - Realistic slippage based on ATR and volume impact
    - Trading fees (0.1% maker/taker)
    - Limit order fill logic
    - Position management with tier exits
    - Trailing stops for runner positions
    
    **Validates: Requirements 7.1, 7.2, 7.4, 7.5, 7.8**
    """
    
    def __init__(
        self,
        data_loader,  # HistoricalDataCollector instance
        config: Optional[BacktestConfig] = None
    ):
        """
        Initialize cycle replay engine.
        
        Args:
            data_loader: HistoricalDataCollector for loading market data
            config: Backtest configuration parameters
        """
        self.data_loader = data_loader
        self.config = config or BacktestConfig()
        
        # State tracking
        self.cash = self.config.initial_capital
        self.equity = self.config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.open_orders: List[Order] = []
        self.closed_trades: List[Dict] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
        # Cycle counter
        self.cycle_count = 0
        
        logger.info(
            f"CycleReplayEngine initialized with capital: ${self.config.initial_capital:,.2f}"
        )
    
    def calculate_slippage(
        self,
        price: float,
        side: OrderSide,
        atr_pct: float,
        volume_impact: float = 0.0
    ) -> float:
        """
        Calculate realistic slippage based on volatility and volume impact.
        
        **Validates: Requirement 7.4**
        
        Slippage model:
        - ATR < 2%: 0.05% base slippage
        - ATR 2-5%: 0.10% base slippage
        - ATR > 5%: 0.15% base slippage
        
        Volume impact:
        - Order size < 0.5% of 24h volume: no additional slippage
        - Order size 0.5-1%: +0.05% slippage
        - Order size > 1%: +0.10% slippage
        
        Args:
            price: Order price
            side: Buy or sell
            atr_pct: ATR as percentage of price
            volume_impact: Order size as fraction of 24h volume
            
        Returns:
            Slippage-adjusted price
        """
        # Base slippage from volatility
        if atr_pct < 2.0:
            base_slippage_pct = 0.05
        elif atr_pct < 5.0:
            base_slippage_pct = 0.10
        else:
            base_slippage_pct = 0.15
        
        # Additional slippage from volume impact
        if volume_impact < 0.005:
            volume_slippage_pct = 0.0
        elif volume_impact < 0.01:
            volume_slippage_pct = 0.05
        else:
            volume_slippage_pct = 0.10
        
        total_slippage_pct = base_slippage_pct + volume_slippage_pct
        
        # Apply slippage direction
        if side == OrderSide.BUY:
            # Buying: price goes up (unfavorable)
            slippage_multiplier = 1 + (total_slippage_pct / 100)
        else:
            # Selling: price goes down (unfavorable)
            slippage_multiplier = 1 - (total_slippage_pct / 100)
        
        slipped_price = price * slippage_multiplier
        
        logger.debug(
            f"Slippage calculation: price={price:.4f}, side={side.value}, "
            f"atr_pct={atr_pct:.2f}%, volume_impact={volume_impact:.4f}, "
            f"total_slippage={total_slippage_pct:.2f}%, slipped_price={slipped_price:.4f}"
        )
        
        return slipped_price
    
    def calculate_fees(
        self,
        notional: float,
        order_type: OrderType
    ) -> float:
        """
        Calculate trading fees.
        
        **Validates: Requirement 7.5**
        
        Args:
            notional: Order notional value (price * quantity)
            order_type: Market or limit order
            
        Returns:
            Fee amount in USD
        """
        if order_type == OrderType.LIMIT:
            fee_pct = self.config.maker_fee_pct
        else:
            fee_pct = self.config.taker_fee_pct
        
        fee = notional * (fee_pct / 100)
        
        logger.debug(
            f"Fee calculation: notional=${notional:.2f}, "
            f"type={order_type.value}, fee_pct={fee_pct}%, fee=${fee:.2f}"
        )
        
        return fee
    
    def check_limit_order_fill(
        self,
        order: Order,
        candle: Dict
    ) -> bool:
        """
        Determine if a limit order should fill based on candle data.
        
        **Validates: Requirement 7.8**
        
        Logic:
        - Buy limit: fills if candle low <= limit price
        - Sell limit: fills if candle high >= limit price
        
        Args:
            order: Limit order to check
            candle: OHLCV candle data
            
        Returns:
            True if order should fill
        """
        if order.order_type != OrderType.LIMIT or order.price is None:
            return False
        
        if order.side == OrderSide.BUY:
            # Buy limit fills if price touches or goes below limit
            return candle['low'] <= order.price
        else:
            # Sell limit fills if price touches or goes above limit
            return candle['high'] >= order.price
    
    async def simulate_cycle(
        self,
        timestamp: datetime,
        market_data: Dict[str, Dict],  # {symbol: {timeframe: candle}}
        signals: Optional[List[Dict]] = None
    ) -> CycleResult:
        """
        Simulate a single 5-minute trading cycle.
        
        **Validates: Requirements 7.1, 7.2**
        
        Cycle flow:
        1. Update open positions with current prices
        2. Check stop losses and take profit targets
        3. Check limit order fills
        4. Process new trading signals
        5. Update equity and metrics
        
        Args:
            timestamp: Current cycle timestamp
            market_data: Market data for all symbols and timeframes
            signals: Optional list of trading signals to process
            
        Returns:
            CycleResult with cycle statistics
        """
        self.cycle_count += 1
        result = CycleResult(timestamp=timestamp)
        
        logger.debug(f"Simulating cycle {self.cycle_count} at {timestamp}")
        
        # 1. Update positions with current prices
        self._update_positions(market_data)
        
        # 2. Check stops and targets
        closed_positions = self._check_exits(market_data, timestamp)
        result.positions_closed = len(closed_positions)
        result.trades.extend(closed_positions)
        
        # 3. Check limit order fills
        filled_orders = self._process_limit_orders(market_data, timestamp)
        result.orders_filled = len(filled_orders)
        
        # 4. Process new signals
        if signals:
            new_positions = self._process_signals(signals, market_data, timestamp)
            result.positions_opened = len(new_positions)
        
        # 5. Update equity
        self._update_equity(market_data)
        result.equity = self.equity
        result.cash = self.cash
        
        # Track equity curve
        self.equity_curve.append((timestamp, self.equity))
        
        logger.debug(
            f"Cycle {self.cycle_count} complete: "
            f"opened={result.positions_opened}, closed={result.positions_closed}, "
            f"equity=${self.equity:,.2f}"
        )
        
        return result
    
    def _update_positions(self, market_data: Dict[str, Dict]) -> None:
        """Update all open positions with current market prices."""
        for position in self.positions.values():
            symbol_data = market_data.get(position.symbol, {})
            candle_5m = symbol_data.get('5m')
            
            if candle_5m:
                position.current_price = candle_5m['close']
                position.highest_price = max(position.highest_price, candle_5m['high'])
    
    def _check_exits(
        self,
        market_data: Dict[str, Dict],
        timestamp: datetime
    ) -> List[Dict]:
        """
        Check stop losses, take profit targets, and trailing stops.
        
        Returns list of closed trade records.
        """
        closed_trades = []
        positions_to_remove = []
        
        for pos_id, position in self.positions.items():
            symbol_data = market_data.get(position.symbol, {})
            candle_5m = symbol_data.get('5m')
            
            if not candle_5m:
                continue
            
            current_price = candle_5m['close']
            low_price = candle_5m['low']
            high_price = candle_5m['high']
            
            # Update position's current price for r_multiple calculation
            position.current_price = current_price
            
            # Check trailing stop first if active (takes priority over regular stop loss)
            if position.trailing_active:
                # Update trailing stop if price moves higher
                new_trailing_stop = current_price * (1 - self.config.runner_trailing_stop_pct)
                if new_trailing_stop > position.trailing_stop:
                    position.trailing_stop = new_trailing_stop
                    logger.debug(f"Trailing stop updated for {position.symbol}: ${position.trailing_stop:.4f}")
                
                # Check if trailing stop hit
                if low_price <= position.trailing_stop:
                    trade = self._close_position(
                        position, position.trailing_stop, timestamp, "trailing_stop"
                    )
                    closed_trades.append(trade)
                    positions_to_remove.append(pos_id)
                    logger.info(f"Trailing stop hit for {position.symbol} @ ${position.trailing_stop:.4f}")
                    continue
            
            # Check stop loss
            if low_price <= position.stop_loss:
                trade = self._close_position(
                    position, position.stop_loss, timestamp, "stop_loss"
                )
                closed_trades.append(trade)
                positions_to_remove.append(pos_id)
                continue
            
            # Check tier exits based on R-multiple
            r_mult = position.r_multiple
            
            # Tier 1: Exit 25% at 2R (use small epsilon for floating point comparison)
            if position.tiers_exited == 0 and r_mult >= (self.config.tier1_target_r - 0.001):
                exit_qty = position.quantity * self.config.tier1_exit_pct
                trade = self._partial_exit(
                    position, exit_qty, current_price, timestamp, "tier1_2R"
                )
                closed_trades.append(trade)
                position.tiers_exited = 1
                logger.info(f"Tier 1 exit (2R) for {position.symbol}: {exit_qty:.4f} @ ${current_price:.4f}")
            
            # Tier 2: Exit 25% at 5R (use small epsilon for floating point comparison)
            elif position.tiers_exited == 1 and r_mult >= (self.config.tier2_target_r - 0.001):
                exit_qty = position.quantity * self.config.tier2_exit_pct
                trade = self._partial_exit(
                    position, exit_qty, current_price, timestamp, "tier2_5R"
                )
                closed_trades.append(trade)
                position.tiers_exited = 2
                position.trailing_active = True
                # Set initial trailing stop
                position.trailing_stop = current_price * (1 - self.config.runner_trailing_stop_pct)
                logger.info(
                    f"Tier 2 exit (5R) for {position.symbol}: {exit_qty:.4f} @ ${current_price:.4f}, "
                    f"trailing stop activated at ${position.trailing_stop:.4f}"
                )
        
        # Remove closed positions
        for pos_id in positions_to_remove:
            del self.positions[pos_id]
        
        return closed_trades
    
    def _close_position(
        self,
        position: Position,
        exit_price: float,
        timestamp: datetime,
        exit_reason: str
    ) -> Dict:
        """Close entire position and return trade record."""
        # Calculate slippage (assume market order)
        atr_pct = 2.0  # Default ATR, should be calculated from data
        slipped_price = self.calculate_slippage(
            exit_price, OrderSide.SELL, atr_pct
        )
        
        # Calculate fees
        notional = slipped_price * position.remaining_quantity
        fees = self.calculate_fees(notional, OrderType.MARKET)
        
        # Calculate PnL
        pnl = (slipped_price - position.entry_price) * position.remaining_quantity - fees
        
        # Update cash
        self.cash += notional - fees
        
        # Create trade record
        trade = {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'side': position.side,
            'entry_price': position.entry_price,
            'exit_price': slipped_price,
            'quantity': position.remaining_quantity,
            'entry_timestamp': position.entry_timestamp,
            'exit_timestamp': timestamp,
            'pnl': pnl,
            'r_multiple': position.r_multiple,
            'setup_type': position.setup_type,
            'exit_reason': exit_reason,
            'fees': fees,
            'slippage': slipped_price - exit_price
        }
        
        self.closed_trades.append(trade)
        
        logger.info(
            f"Position closed: {position.symbol} {exit_reason}, "
            f"PnL: ${pnl:.2f}, R: {position.r_multiple:.2f}R"
        )
        
        return trade
    
    def _partial_exit(
        self,
        position: Position,
        exit_quantity: float,
        exit_price: float,
        timestamp: datetime,
        exit_reason: str
    ) -> Dict:
        """Partially exit position and return trade record."""
        # Calculate slippage
        atr_pct = 2.0  # Default ATR
        slipped_price = self.calculate_slippage(
            exit_price, OrderSide.SELL, atr_pct
        )
        
        # Calculate fees
        notional = slipped_price * exit_quantity
        fees = self.calculate_fees(notional, OrderType.MARKET)
        
        # Calculate PnL for this partial exit
        pnl = (slipped_price - position.entry_price) * exit_quantity - fees
        
        # Update position
        position.remaining_quantity -= exit_quantity
        self.cash += notional - fees
        
        # Create trade record
        trade = {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'side': position.side,
            'entry_price': position.entry_price,
            'exit_price': slipped_price,
            'quantity': exit_quantity,
            'entry_timestamp': position.entry_timestamp,
            'exit_timestamp': timestamp,
            'pnl': pnl,
            'r_multiple': (slipped_price - position.entry_price) / (position.entry_price - position.stop_loss),
            'setup_type': position.setup_type,
            'exit_reason': exit_reason,
            'fees': fees,
            'slippage': slipped_price - exit_price,
            'partial': True
        }
        
        position.trades.append(trade)
        
        return trade
    
    def _process_limit_orders(
        self,
        market_data: Dict[str, Dict],
        timestamp: datetime
    ) -> List[Order]:
        """Process open limit orders and fill if conditions met."""
        filled_orders = []
        orders_to_remove = []
        
        for i, order in enumerate(self.open_orders):
            symbol_data = market_data.get(order.symbol, {})
            candle_5m = symbol_data.get('5m')
            
            if not candle_5m:
                continue
            
            if self.check_limit_order_fill(order, candle_5m):
                # Fill the order
                order.filled = True
                order.fill_price = order.price
                order.fill_timestamp = timestamp
                
                filled_orders.append(order)
                orders_to_remove.append(i)
                
                logger.info(
                    f"Limit order filled: {order.symbol} {order.side.value} "
                    f"{order.quantity:.4f} @ ${order.fill_price:.4f}"
                )
        
        # Remove filled orders
        for i in reversed(orders_to_remove):
            self.open_orders.pop(i)
        
        return filled_orders
    
    def _process_signals(
        self,
        signals: List[Dict],
        market_data: Dict[str, Dict],
        timestamp: datetime
    ) -> List[Position]:
        """Process trading signals and open new positions."""
        new_positions = []
        
        # Check if we can open more positions
        if len(self.positions) >= self.config.max_positions:
            logger.debug(f"Max positions ({self.config.max_positions}) reached, skipping signals")
            return new_positions
        
        for signal in signals:
            # Check if signal meets threshold
            if signal.get('posterior', 0) < self.config.bayesian_threshold:
                continue
            
            # Calculate position size
            symbol = signal['symbol']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            
            risk_per_share = entry_price - stop_loss
            if risk_per_share <= 0:
                logger.warning(f"Invalid risk for {symbol}: entry={entry_price}, stop={stop_loss}")
                continue
            
            risk_amount = self.cash * self.config.position_size_pct
            quantity = risk_amount / risk_per_share
            
            # Check if we have enough cash
            notional = entry_price * quantity
            if notional > self.cash:
                logger.warning(f"Insufficient cash for {symbol}: need ${notional:.2f}, have ${self.cash:.2f}")
                continue
            
            # Calculate slippage and fees
            atr_pct = signal.get('atr_pct', 2.0)
            slipped_price = self.calculate_slippage(entry_price, OrderSide.BUY, atr_pct)
            fees = self.calculate_fees(slipped_price * quantity, OrderType.MARKET)
            
            # Create position
            position = Position(
                position_id=f"pos_{timestamp.strftime('%Y%m%d_%H%M%S')}_{symbol.replace('/', '_')}",
                symbol=symbol,
                side="long",
                entry_price=slipped_price,
                quantity=quantity,
                remaining_quantity=quantity,
                stop_loss=stop_loss,
                take_profit=signal.get('take_profit', entry_price * 1.5),
                setup_type=signal.get('setup_type', 'unknown'),
                posterior=signal['posterior'],
                entry_timestamp=timestamp,
                current_price=slipped_price,
                highest_price=slipped_price
            )
            
            # Update cash
            self.cash -= (slipped_price * quantity + fees)
            
            # Add to positions
            self.positions[position.position_id] = position
            new_positions.append(position)
            
            logger.info(
                f"Position opened: {symbol} {quantity:.4f} @ ${slipped_price:.4f}, "
                f"stop=${stop_loss:.4f}, posterior={signal['posterior']:.3f}"
            )
        
        return new_positions
    
    def _update_equity(self, market_data: Dict[str, Dict]) -> None:
        """Calculate total equity (cash + unrealized PnL)."""
        unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        self.equity = self.cash + unrealized_pnl
    
    async def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        signals_generator=None  # Optional function to generate signals per cycle
    ) -> BacktestResult:
        """
        Execute complete backtest simulation.
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            signals_generator: Optional function(timestamp, market_data) -> List[signals]
            
        Returns:
            BacktestResult with complete statistics
        """
        logger.info(
            f"Starting backtest: {start_date} to {end_date}, "
            f"{len(symbols)} symbols, capital=${self.config.initial_capital:,.2f}"
        )
        
        # Reset state
        self.cash = self.config.initial_capital
        self.equity = self.config.initial_capital
        self.positions = {}
        self.open_orders = []
        self.closed_trades = []
        self.equity_curve = []
        self.cycle_count = 0
        
        # Generate 5-minute timestamps
        current_time = start_date
        cycle_interval = timedelta(minutes=5)
        
        while current_time <= end_date:
            # Load market data for this timestamp
            # In real implementation, this would load from historical data
            market_data = {}  # Placeholder
            
            # Generate signals if generator provided
            signals = None
            if signals_generator:
                signals = signals_generator(current_time, market_data)
            
            # Simulate cycle
            await self.simulate_cycle(current_time, market_data, signals)
            
            # Advance to next cycle
            current_time += cycle_interval
        
        # Create result
        equity_series = pd.Series(
            [eq for _, eq in self.equity_curve],
            index=[ts for ts, _ in self.equity_curve]
        )
        
        winning_trades = len([t for t in self.closed_trades if t['pnl'] > 0])
        losing_trades = len([t for t in self.closed_trades if t['pnl'] <= 0])
        total_pnl = sum(t['pnl'] for t in self.closed_trades)
        
        result = BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.config.initial_capital,
            final_equity=self.equity,
            total_trades=len(self.closed_trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            equity_curve=equity_series,
            trades=self.closed_trades,
            config=self.config
        )
        
        logger.info(
            f"Backtest complete: {result.total_trades} trades, "
            f"win_rate={result.win_rate:.2%}, PnL=${result.total_pnl:,.2f}, "
            f"profit_factor={result.profit_factor:.2f}"
        )
        
        return result
