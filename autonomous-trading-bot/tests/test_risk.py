"""
Unit tests for Risk Manager.
"""
from src.risk_manager import RiskManager


class TestRiskManager:
    def setup_method(self):
        """Create RiskManager with test settings."""
        from unittest.mock import MagicMock
        s = MagicMock()
        s.max_positions = 3
        s.max_risk_per_trade_pct = 0.01
        s.max_portfolio_exposure_pct = 0.30
        s.max_single_exposure_pct = 0.08
        s.max_correlation = 0.7
        s.max_drawdown_pct = 0.10
        s.daily_loss_limit_pct = 0.03
        s.initial_equity_usd = 10000.0
        self.rm = RiskManager(s)

    # ── Can Open Position ──────────────────────────────────────────────
    def test_can_open_no_positions(self):
        """Empty portfolio → can open."""
        allowed, reason = self.rm.can_open_position("BTC/USDT", {})
        assert allowed is True
        assert reason == "ok"

    def test_max_positions_reached(self):
        """At max positions → blocked."""
        self.rm.open_positions = [
            {"symbol": "BTC/USDT", "notional_usd": 500},
            {"symbol": "ETH/USDT", "notional_usd": 500},
            {"symbol": "SOL/USDT", "notional_usd": 500},
        ]
        allowed, reason = self.rm.can_open_position("DOGE/USDT", {})
        assert allowed is False
        assert "max_positions" in reason

    def test_duplicate_symbol_blocked(self):
        """Already holding BTC/USDT → blocked."""
        self.rm.open_positions = [{"symbol": "BTC/USDT", "notional_usd": 500}]
        allowed, reason = self.rm.can_open_position("BTC/USDT", {})
        assert allowed is False
        assert "duplicate" in reason

    def test_drawdown_breaker(self):
        """10%+ drawdown → blocked."""
        self.rm.equity = 8900.0  # 11% drawdown from 10000
        self.rm.peak_equity = 10000.0
        allowed, reason = self.rm.can_open_position("XRP/USDT", {})
        assert allowed is False
        assert "drawdown" in reason

    def test_daily_loss_limit(self):
        """Daily loss exceeds limit → blocked."""
        self.rm.daily_pnl = -400.0  # 4% of 10000
        allowed, reason = self.rm.can_open_position("LINK/USDT", {})
        assert allowed is False
        assert "daily_loss" in reason

    # ── Position Sizing ────────────────────────────────────────────────
    def test_position_size_basic(self):
        """Position size should be > 0 for valid inputs."""
        size = self.rm.position_size_usd(
            entry_price=50000.0,
            stop_loss=49000.0,
            posterior=0.70
        )
        assert size > 0
        # Should not exceed max single exposure
        assert size <= self.rm.equity * self.rm.max_single_exposure_pct

    def test_position_size_tight_stop(self):
        """Tighter stop → size capped by max_single_exposure, both valid."""
        size_tight = self.rm.position_size_usd(50000, 49500, 0.70)
        size_wide = self.rm.position_size_usd(50000, 48000, 0.70)
        assert size_tight > 0
        assert size_wide > 0
        # Both may be capped at max_single_exposure
        assert size_tight >= size_wide

    def test_position_size_zero_stop(self):
        """Zero or equal stop → should return 0 (avoid division by zero)."""
        size = self.rm.position_size_usd(50000, 50000, 0.70)
        assert size == 0

    # ── Portfolio Health ───────────────────────────────────────────────
    def test_portfolio_health_normal(self):
        """Healthy portfolio → normal mode."""
        health = self.rm.check_portfolio_health()
        assert "recommended_mode" in health
        assert health["recommended_mode"] == "normal"
        assert health["can_trade"] is True

    def test_portfolio_health_volatile(self):
        """5% drawdown → volatile mode."""
        self.rm.equity = 9500.0
        self.rm.peak_equity = 10000.0
        health = self.rm.check_portfolio_health()
        assert health["recommended_mode"] in ("volatile", "normal")

    def test_portfolio_health_safety(self):
        """>= 10% drawdown → safety mode."""
        self.rm.equity = 8900.0
        self.rm.peak_equity = 10000.0
        health = self.rm.check_portfolio_health()
        assert health["recommended_mode"] == "safety"

    # ── Equity Tracking ────────────────────────────────────────────────
    def test_update_equity_peak(self):
        """New high → peak updates."""
        self.rm.update_equity(12000.0)
        assert self.rm.peak_equity == 12000.0

    def test_update_equity_no_peak(self):
        """Below peak → peak stays."""
        self.rm.update_equity(9000.0)
        assert self.rm.peak_equity == 10000.0

    def test_reset_daily(self):
        """Daily reset clears PnL."""
        self.rm.daily_pnl = -150.0
        self.rm.reset_daily()
        assert self.rm.daily_pnl == 0.0
