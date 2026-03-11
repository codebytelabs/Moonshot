"""
Risk Manager — Portfolio-level risk controls.
Kelly-informed sizing, max positions, exposure limits, drawdown breaker,
daily loss limit, correlation checks, and portfolio heat monitoring.
"""
import math
from typing import Optional
from datetime import datetime, timedelta
from loguru import logger

from .config import Settings


class RiskManager:
    """
    Controls position sizing and enforces portfolio risk constraints.

    Key responsibilities:
    - Position size computation (Kelly-informed)
    - Max position cap enforcement
    - Portfolio exposure limits
    - Daily loss limit
    - Drawdown circuit breaker
    - Correlation-based overlap rejection
    """

    def __init__(self, settings: Settings):
        self.max_positions = settings.max_positions
        self.max_risk_per_trade_pct = settings.max_risk_per_trade_pct
        self.max_portfolio_exposure_pct = settings.max_portfolio_exposure_pct
        self.max_single_exposure_pct = settings.max_single_exposure_pct
        self.max_correlation = settings.max_correlation
        self.max_drawdown_pct = settings.max_drawdown_pct
        self.daily_loss_limit_pct = settings.daily_loss_limit_pct

        # Tracked state
        self.equity = settings.initial_equity_usd
        self.peak_equity = self.equity
        self.daily_pnl = 0.0
        self.open_positions: list[dict] = []
        
        # Half-Kelly parameters
        self.kelly_win_rate: Optional[float] = None
        self.kelly_avg_win_loss_ratio: Optional[float] = None
        self.kelly_last_update: Optional[datetime] = None
        self.kelly_trade_count: int = 0
        self.min_trades_for_kelly: int = 30
        self.conservative_default_fraction: float = 0.10
        self.max_kelly_fraction: float = 0.25
        
        # Store reference for historical trade queries
        self.store = None

    def update_equity(self, new_equity: float):
        """Update current equity and track peak."""
        self.equity = new_equity
        if new_equity > self.peak_equity:
            self.peak_equity = new_equity

    def update_daily_pnl(self, pnl: float):
        """Add to daily PnL (reset daily)."""
        self.daily_pnl += pnl

    def reset_daily(self):
        """Reset daily metrics (call at start of each trading day)."""
        self.daily_pnl = 0.0

    def set_open_positions(self, positions: list[dict]):
        """Update current open positions."""
        self.open_positions = positions
    
    def set_store(self, store):
        """Set the SupabaseStore reference for historical trade queries."""
        self.store = store

    def update_kelly_parameters(self, force: bool = False):
        """
        Update Kelly parameters from rolling 90-day trade history.
        Updates monthly or when forced.
        
        Requirements: 23.2, 23.5, 23.6
        """
        # Check if update is needed
        if not force and self.kelly_last_update:
            days_since_update = (datetime.now() - self.kelly_last_update).days
            if days_since_update < 30:
                logger.debug(f"Kelly parameters updated {days_since_update} days ago, skipping")
                return
        
        if not self.store:
            logger.warning("No store available for Kelly parameter update, using defaults")
            return
        
        # Query trades from last 90 days
        try:
            from datetime import timezone
            ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
            
            # Get all trades (we'll filter by date)
            all_trades = self.store.get_recent_trades(n=1000)
            
            # Filter to last 90 days and completed trades with PnL
            recent_trades = []
            for trade in all_trades:
                if trade.get('pnl') is None:
                    continue
                    
                trade_time_str = trade.get('created_at', '')
                if not trade_time_str:
                    continue
                    
                try:
                    trade_time = datetime.fromisoformat(trade_time_str.replace('Z', '+00:00'))
                    if trade_time >= ninety_days_ago:
                        recent_trades.append(trade)
                except (ValueError, AttributeError):
                    continue
            
            self.kelly_trade_count = len(recent_trades)
            
            # Need minimum trades for reliable Kelly calculation
            if self.kelly_trade_count < self.min_trades_for_kelly:
                logger.info(
                    f"Insufficient trade history ({self.kelly_trade_count} < {self.min_trades_for_kelly}), "
                    f"using conservative default f={self.conservative_default_fraction}"
                )
                self.kelly_win_rate = None
                self.kelly_avg_win_loss_ratio = None
                self.kelly_last_update = datetime.now()
                return
            
            # Calculate win rate
            winning_trades = [t for t in recent_trades if t['pnl'] > 0]
            self.kelly_win_rate = len(winning_trades) / len(recent_trades)
            
            # Calculate average win/loss ratio
            avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
            losing_trades = [t for t in recent_trades if t['pnl'] < 0]
            avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 1
            
            self.kelly_avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0
            self.kelly_last_update = datetime.now()
            
            logger.info(
                f"Kelly parameters updated: win_rate={self.kelly_win_rate:.3f}, "
                f"avg_win_loss_ratio={self.kelly_avg_win_loss_ratio:.3f}, "
                f"trades={self.kelly_trade_count}"
            )
            
        except Exception as e:
            logger.error(f"Failed to update Kelly parameters: {e}")
            self.kelly_win_rate = None
            self.kelly_avg_win_loss_ratio = None

    def calculate_half_kelly_fraction(self) -> float:
        """
        Calculate half-Kelly fraction: f = 0.5 × (p × (b + 1) - 1) / b
        
        Where:
        - p = historical win rate
        - b = average win / average loss ratio
        
        Returns fraction capped at max_kelly_fraction (0.25).
        Returns conservative default if insufficient trade history.
        Returns 0 if Kelly fraction is negative (no edge).
        
        Requirements: 23.1, 23.2, 23.3, 23.4, 23.6
        """
        # Use conservative default if insufficient history
        if self.kelly_trade_count < self.min_trades_for_kelly:
            return self.conservative_default_fraction
        
        # Need valid parameters
        if self.kelly_win_rate is None or self.kelly_avg_win_loss_ratio is None:
            return self.conservative_default_fraction
        
        p = self.kelly_win_rate
        b = self.kelly_avg_win_loss_ratio
        
        # Avoid division by zero
        if b <= 0:
            return self.conservative_default_fraction
        
        # Full Kelly: f = (p × (b + 1) - 1) / b
        full_kelly = (p * (b + 1) - 1) / b
        
        # Half-Kelly for safety
        half_kelly = 0.5 * full_kelly
        
        # Reject negative Kelly (no edge)
        if half_kelly < 0:
            logger.debug(f"Negative Kelly fraction ({half_kelly:.4f}), rejecting trade")
            return 0.0
        
        # Cap at maximum
        capped_kelly = min(half_kelly, self.max_kelly_fraction)
        
        logger.debug(
            f"Kelly calculation: p={p:.3f}, b={b:.3f}, "
            f"full_kelly={full_kelly:.4f}, half_kelly={half_kelly:.4f}, "
            f"capped={capped_kelly:.4f}"
        )
        
        return capped_kelly

    # ── Pre-trade checks ────────────────────────────────────────────────

    def can_open_position(self, symbol: str, setup: dict) -> tuple[bool, str]:
        """
        Check if a new position is allowed.
        Returns (allowed, reason).
        """
        # Max positions
        if len(self.open_positions) >= self.max_positions:
            return False, f"max_positions_reached ({self.max_positions})"

        # Drawdown breaker
        drawdown = self._current_drawdown()
        if drawdown >= self.max_drawdown_pct:
            return False, f"drawdown_limit ({drawdown:.1%} >= {self.max_drawdown_pct:.1%})"

        # Daily loss limit
        daily_loss_pct = abs(self.daily_pnl) / self.equity if self.equity > 0 else 0
        if self.daily_pnl < 0 and daily_loss_pct >= self.daily_loss_limit_pct:
            return False, f"daily_loss_limit ({daily_loss_pct:.1%} >= {self.daily_loss_limit_pct:.1%})"

        # Portfolio exposure
        current_exposure = self._total_exposure()
        if current_exposure >= self.max_portfolio_exposure_pct:
            return False, f"portfolio_exposure_limit ({current_exposure:.1%} >= {self.max_portfolio_exposure_pct:.1%})"

        # Duplicate symbol check
        for pos in self.open_positions:
            if pos.get("symbol") == symbol:
                return False, "duplicate_position"

        # Correlation check (simplified — same base currency overlap)
        base = symbol.split("/")[0] if "/" in symbol else symbol
        for pos in self.open_positions:
            pos_base = pos.get("symbol", "").split("/")[0]
            if pos_base == base:
                return False, f"correlated_position ({base})"

        return True, "ok"

    def position_size_usd(self, entry_price: float, stop_loss: float, posterior: float = 0.65) -> float:
        """
        Compute position size in USD using half-Kelly formula.
        
        Formula: f = 0.5 × (p × (b + 1) - 1) / b
        Where:
        - p = historical win rate
        - b = average win / average loss ratio
        
        Position size = (equity × kelly_fraction) / risk_per_unit
        
        Constraints:
        - Cap Kelly fraction at 0.25 (25% of equity)
        - Reject trades with negative Kelly fraction
        - Use conservative default (0.10) for <30 trades
        - Apply max_single_exposure and max_portfolio_exposure limits
        
        Requirements: 23.1, 23.2, 23.3, 23.4, 23.6, 23.7, 23.8
        """
        if entry_price <= 0 or stop_loss <= 0 or entry_price <= stop_loss:
            return 0.0

        risk_per_unit = (entry_price - stop_loss) / entry_price

        if risk_per_unit <= 0 or risk_per_unit >= 1:
            return 0.0

        # Calculate half-Kelly fraction
        kelly_fraction = self.calculate_half_kelly_fraction()
        
        # Reject trade if Kelly fraction is zero (negative edge or insufficient data with no default)
        if kelly_fraction <= 0:
            logger.debug("Kelly fraction is zero or negative, rejecting trade")
            return 0.0

        # Dollar risk based on Kelly fraction
        risk_dollars = self.equity * kelly_fraction
        if risk_dollars <= 0:
            return 0.0

        # Position size = risk_dollars / risk_per_unit
        size_usd = risk_dollars / risk_per_unit

        # Apply max single exposure constraint
        max_size = self.equity * self.max_single_exposure_pct
        size_usd = min(size_usd, max_size)

        # Apply max portfolio exposure constraint
        remaining_exposure = (self.max_portfolio_exposure_pct - self._total_exposure()) * self.equity
        size_usd = min(size_usd, max(0, remaining_exposure))

        logger.debug(
            f"Position size: kelly_fraction={kelly_fraction:.4f} "
            f"risk_dollars=${risk_dollars:.2f} size=${size_usd:.2f}"
        )
        return round(size_usd, 2)

    def check_portfolio_health(self) -> dict:
        """Return a health summary of the portfolio."""
        drawdown = self._current_drawdown()
        exposure = self._total_exposure()
        daily_loss_pct = abs(self.daily_pnl) / self.equity if self.equity > 0 else 0

        # Determine mode recommendation
        if drawdown >= self.max_drawdown_pct * 0.8:
            recommended_mode = "safety"
        elif drawdown >= self.max_drawdown_pct * 0.5 or daily_loss_pct >= self.daily_loss_limit_pct * 0.7:
            recommended_mode = "volatile"
        else:
            recommended_mode = "normal"

        return {
            "equity": round(self.equity, 2),
            "peak_equity": round(self.peak_equity, 2),
            "drawdown_pct": round(drawdown, 4),
            "total_exposure_pct": round(exposure, 4),
            "open_positions": len(self.open_positions),
            "max_positions": self.max_positions,
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_pct": round(daily_loss_pct, 4),
            "recommended_mode": recommended_mode,
            "can_trade": drawdown < self.max_drawdown_pct and (self.daily_pnl >= 0 or daily_loss_pct < self.daily_loss_limit_pct),
        }

    # ── Internal helpers ────────────────────────────────────────────────

    def _current_drawdown(self) -> float:
        """Current drawdown from peak equity."""
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.equity) / self.peak_equity

    def _total_exposure(self) -> float:
        """Total portfolio exposure as fraction of equity."""
        if self.equity <= 0:
            return 0.0
        total = sum(pos.get("notional_usd", 0) for pos in self.open_positions)
        return total / self.equity
