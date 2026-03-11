"""
Position Manager — Full position lifecycle management.
Entry, tier exits (25% at 2R, 25% at 5R, 50% runner with trailing stop),
pyramiding, stop-loss tracking, and state persistence.
"""
import uuid
import time
from typing import Optional
from loguru import logger

from .exchange_ccxt import ExchangeConnector
from .supabase_client import SupabaseStore
from .config import Settings
from .metrics import active_positions, trades_total


class PositionState:
    """Enum-like states for position lifecycle."""
    PENDING = "pending"
    OPEN = "open"
    PARTIAL = "partial"     # some tiers exited
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Position:
    """
    Tracks a single position through its lifecycle.
    Manages entry, tier exits, trailing stops, and PnL calculation.
    """

    def __init__(
        self,
        symbol: str,
        side: str,        # "long" only for now
        entry_price: float,
        quantity: float,
        stop_loss: float,
        take_profit: float,
        setup_type: str,
        posterior: float,
        position_id: Optional[str] = None,
        exchange: str = "gateio",
    ):
        self.id = position_id or str(uuid.uuid4())[:12]
        self.symbol = symbol
        self.side = side
        self.exchange = exchange
        self.entry_price = entry_price
        self.quantity = quantity  # total quantity at entry
        self.remaining_quantity = quantity
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.setup_type = setup_type
        self.posterior = posterior
        self.status = PositionState.OPEN
        self.created_at = time.time()

        # Tracking
        self.current_price = entry_price
        self.highest_price = entry_price
        self.trades: list[dict] = []
        self.tiers_exited = 0
        self.trailing_active = False
        self.trailing_stop = 0.0
        self.pyramid_count = 0
        self.total_cost = entry_price * quantity
        self.total_sold = 0.0

    @property
    def notional_usd(self) -> float:
        return self.remaining_quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.remaining_quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price

    @property
    def r_multiple(self) -> float:
        """Current R-multiple (risk units of profit)."""
        risk = self.entry_price - self.stop_loss
        if risk <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / risk

    @property
    def realized_pnl(self) -> float:
        return sum(t.get("pnl", 0) for t in self.trades)

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "exchange": self.exchange,
            "status": self.status,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "quantity": self.quantity,
            "remaining_quantity": self.remaining_quantity,
            "notional_usd": self.notional_usd,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "r_multiple": round(self.r_multiple, 2),
            "setup_type": self.setup_type,
            "tiers_exited": self.tiers_exited,
            "trailing_active": self.trailing_active,
            "trailing_stop": self.trailing_stop,
            "created_at": self.created_at,
        }


class PositionManager:
    """
    Manages all open positions, handling:
    - Entry execution
    - Tier-based profit taking (25% at 2R, 25% at 5R, 50% runner)
    - Trailing stop management
    - Stop-loss execution
    - Optional pyramiding
    - State persistence to Supabase
    """

    def __init__(
        self,
        exchange: ExchangeConnector,
        settings: Settings,
        store: Optional[SupabaseStore] = None,
        paper_mode: bool = True,
    ):
        self.exchange = exchange
        self.settings = settings
        self.store = store
        self.paper_mode = paper_mode

        # Tier config from settings
        self.tier1_r = settings.tier1_r_multiple
        self.tier1_pct = settings.tier1_exit_pct
        self.tier2_r = settings.tier2_r_multiple
        self.tier2_pct = settings.tier2_exit_pct
        self.runner_trailing_pct = settings.runner_trailing_stop_pct
        self.pyramid_enabled = settings.pyramid_enabled
        self.pyramid_max_adds = settings.pyramid_max_adds
        self.pyramid_min_r = settings.pyramid_min_r_to_add

        # Active positions
        self.positions: dict[str, Position] = {}

    def get_open_positions(self) -> list[dict]:
        """Get all open positions as dicts."""
        return [p.to_dict() for p in self.positions.values() if p.status in (PositionState.OPEN, PositionState.PARTIAL)]

    def get_position(self, position_id: str) -> Optional[Position]:
        return self.positions.get(position_id)

    # ── Entry ───────────────────────────────────────────────────────────

    async def open_position(
        self,
        symbol: str,
        size_usd: float,
        entry_zone: dict,
        setup_type: str,
        posterior: float,
    ) -> Optional[Position]:
        """Open a new position."""
        entry_price = entry_zone.get("entry", 0)
        stop_loss = entry_zone.get("stop_loss", 0)
        take_profit = entry_zone.get("take_profit", 0)

        if entry_price <= 0 or stop_loss <= 0:
            logger.error(f"Invalid entry zone for {symbol}: {entry_zone}")
            return None

        # Compute quantity
        quantity = size_usd / entry_price

        # Precision
        try:
            quantity = self.exchange.amount_to_precision(symbol, quantity)
        except Exception:
            pass

        if self.paper_mode:
            logger.info(f"📝 PAPER BUY {symbol}: qty={quantity} @ ${entry_price:.6f} (${size_usd:.2f})")
        else:
            try:
                order = await self.exchange.create_market_buy(symbol, quantity)
                entry_price = order.get("average", entry_price)
                quantity = order.get("filled", quantity)
                logger.info(f"✅ LIVE BUY {symbol}: qty={quantity} @ ${entry_price:.6f}")
            except Exception as e:
                logger.error(f"❌ Failed to open {symbol}: {e}")
                return None

        # Create position object
        pos = Position(
            symbol=symbol,
            side="long",
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            setup_type=setup_type,
            posterior=posterior,
        )

        self.positions[pos.id] = pos
        active_positions.inc()
        trades_total.labels(exchange=self.exchange.name, symbol=symbol, side="buy", mode="paper" if self.paper_mode else "live").inc()

        # Record trade
        trade = {
            "type": "entry",
            "price": entry_price,
            "quantity": quantity,
            "notional_usd": size_usd,
            "pnl": 0,
            "timestamp": time.time(),
        }
        pos.trades.append(trade)

        # Persist
        self._persist_position(pos)
        self._persist_trade(pos, trade)

        logger.info(f"Position opened: {pos.id} {symbol} stop={stop_loss:.6f} target={take_profit:.6f}")
        return pos

    # ── Price Update & Exit Logic ───────────────────────────────────────

    async def update_prices(self, tickers: dict):
        """Update prices and check exit conditions for all positions."""
        for pos_id, pos in list(self.positions.items()):
            if pos.status not in (PositionState.OPEN, PositionState.PARTIAL):
                continue

            ticker = tickers.get(pos.symbol, {})
            current_price = ticker.get("last", pos.current_price)
            if current_price <= 0:
                continue

            pos.current_price = current_price
            pos.highest_price = max(pos.highest_price, current_price)

            # Check exits
            await self._check_stop_loss(pos)
            await self._check_tier_exits(pos)
            await self._check_trailing_stop(pos)

            # Persist updated state
            self._persist_position(pos)

    async def _check_stop_loss(self, pos: Position):
        """Close position if price hits stop loss."""
        if pos.current_price <= pos.stop_loss:
            logger.warning(f"🛑 STOP LOSS HIT {pos.symbol} @ ${pos.current_price:.6f} (stop=${pos.stop_loss:.6f})")
            await self._close_position(pos, "stop_loss")

    async def _check_tier_exits(self, pos: Position):
        """Execute tier-based profit taking."""
        r = pos.r_multiple

        # Tier 1: 25% at 2R
        if pos.tiers_exited < 1 and r >= self.tier1_r:
            sell_qty = pos.quantity * self.tier1_pct
            sell_qty = min(sell_qty, pos.remaining_quantity)
            await self._partial_exit(pos, sell_qty, f"tier1_{self.tier1_r}R")
            pos.tiers_exited = 1

        # Tier 2: 25% at 5R
        if pos.tiers_exited < 2 and r >= self.tier2_r:
            sell_qty = pos.quantity * self.tier2_pct
            sell_qty = min(sell_qty, pos.remaining_quantity)
            await self._partial_exit(pos, sell_qty, f"tier2_{self.tier2_r}R")
            pos.tiers_exited = 2

            # Activate trailing stop for runner
            pos.trailing_active = True
            pos.trailing_stop = pos.current_price * (1 - self.runner_trailing_pct)
            logger.info(f"🎯 Trailing stop activated for {pos.symbol} @ ${pos.trailing_stop:.6f}")

    async def _check_trailing_stop(self, pos: Position):
        """Update and check trailing stop for runner portion."""
        if not pos.trailing_active:
            return

        # Update trailing stop
        new_trail = pos.highest_price * (1 - self.runner_trailing_pct)
        if new_trail > pos.trailing_stop:
            pos.trailing_stop = new_trail

        # Check if hit
        if pos.current_price <= pos.trailing_stop:
            logger.info(f"📈 TRAILING STOP {pos.symbol} @ ${pos.current_price:.6f} (trail=${pos.trailing_stop:.6f})")
            await self._close_position(pos, "trailing_stop")

    async def _partial_exit(self, pos: Position, quantity: float, reason: str):
        """Execute a partial exit."""
        try:
            quantity = self.exchange.amount_to_precision(pos.symbol, quantity)
        except Exception:
            pass

        if quantity <= 0:
            return

        pnl = (pos.current_price - pos.entry_price) * quantity

        if self.paper_mode:
            logger.info(f"📝 PAPER SELL {pos.symbol}: qty={quantity} @ ${pos.current_price:.6f} ({reason}) PnL=${pnl:.2f}")
        else:
            try:
                await self.exchange.create_market_sell(pos.symbol, quantity)
            except Exception as e:
                logger.error(f"❌ Partial exit failed {pos.symbol}: {e}")
                return

        pos.remaining_quantity -= quantity
        pos.total_sold += pos.current_price * quantity
        if pos.remaining_quantity > 0:
            pos.status = PositionState.PARTIAL
        else:
            pos.status = PositionState.CLOSED
            active_positions.dec()

        trade = {
            "type": reason,
            "price": pos.current_price,
            "quantity": quantity,
            "notional_usd": pos.current_price * quantity,
            "pnl": round(pnl, 2),
            "r_multiple": round(pos.r_multiple, 2),
            "timestamp": time.time(),
        }
        pos.trades.append(trade)
        trades_total.labels(exchange=self.exchange.name, symbol=pos.symbol, side="sell", mode="paper" if self.paper_mode else "live").inc()

        self._persist_trade(pos, trade)

    async def _close_position(self, pos: Position, reason: str):
        """Fully close remaining position."""
        if pos.remaining_quantity <= 0:
            pos.status = PositionState.CLOSED
            return

        await self._partial_exit(pos, pos.remaining_quantity, reason)

        if pos.status != PositionState.CLOSED:
            pos.status = PositionState.CLOSED
            active_positions.dec()

        logger.info(f"Position closed: {pos.id} {pos.symbol} total_pnl=${pos.total_pnl:.2f} R={pos.r_multiple:.2f}")

    # ── Persistence ─────────────────────────────────────────────────────

    def _persist_position(self, pos: Position):
        """Save position to Supabase."""
        if not self.store:
            return
        self.store.upsert_position(
            position_id=pos.id,
            symbol=pos.symbol,
            side=pos.side,
            status=pos.status,
            entry_price=pos.entry_price,
            current_price=pos.current_price,
            quantity=pos.quantity,
            notional_usd=pos.notional_usd,
            unrealized_pnl=pos.unrealized_pnl,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            exchange=pos.exchange,
        )

    def _persist_trade(self, pos: Position, trade: dict):
        """Save trade to Supabase."""
        if not self.store:
            return
        self.store.insert_trade(
            position_id=pos.id,
            symbol=pos.symbol,
            side="sell" if "exit" in trade.get("type", "") or trade.get("type") in ("stop_loss", "trailing_stop", "tier1_2.0R", "tier2_5.0R") else "buy",
            price=trade["price"],
            quantity=trade["quantity"],
            notional_usd=trade["notional_usd"],
            trade_type=trade["type"],
            pnl=trade.get("pnl"),
            r_multiple=trade.get("r_multiple"),
        )
