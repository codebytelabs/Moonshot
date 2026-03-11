"""
Unit tests for BigBrother Agent.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.bigbrother import BigBrotherAgent
from src.risk_manager import RiskManager
from src.bayesian_engine import BayesianDecisionEngine


class TestBigBrother:
    def setup_method(self):
        """Set up BigBrother with mock dependencies."""
        # Mock settings for RiskManager
        s = MagicMock()
        s.max_positions = 5
        s.max_risk_per_trade_pct = 0.01
        s.max_portfolio_exposure_pct = 0.30
        s.max_single_exposure_pct = 0.08
        s.max_correlation = 0.7
        s.max_drawdown_pct = 0.10
        s.daily_loss_limit_pct = 0.03
        s.initial_equity_usd = 10000.0

        self.risk = RiskManager(s)
        self.engine = BayesianDecisionEngine(store=MagicMock(), mode="normal")
        self.store = MagicMock()
        self.alert_fn = AsyncMock()
        self.bb = BigBrotherAgent(
            risk_manager=self.risk,
            decision_engine=self.engine,
            store=self.store,
            alert_fn=self.alert_fn,
        )

    @pytest.mark.asyncio
    async def test_supervise_normal(self):
        """Normal portfolio → no mode change, no events."""
        result = await self.bb.supervise()
        assert result["mode"] == "normal"
        assert len(result["events"]) == 0

    @pytest.mark.asyncio
    async def test_supervise_mode_change(self):
        """Trigger drawdown → mode change to safety."""
        self.risk.equity = 8900.0
        self.risk.peak_equity = 10000.0
        result = await self.bb.supervise()
        assert result["mode"] == "safety"
        assert any(e["type"] == "mode_change" for e in result["events"])
        # Alert should be called
        self.alert_fn.assert_called()

    @pytest.mark.asyncio
    async def test_supervise_trading_halt(self):
        """Severe situation → trading halted event."""
        self.risk.equity = 8000.0
        self.risk.peak_equity = 10000.0
        self.risk.daily_pnl = -500.0
        result = await self.bb.supervise()
        # Should be in safety mode
        assert result["mode"] == "safety"

    def test_record_trade(self):
        """Recording a trade updates results."""
        self.bb.record_trade_result({"pnl": 50, "r_multiple": 1.5, "setup_type": "breakout"})
        assert len(self.bb.trade_results) == 1

    def test_status_summary(self):
        """Status summary returns expected keys."""
        summary = self.bb.get_status_summary()
        assert "mode" in summary
        assert "health" in summary
        assert "total_trades" in summary
        assert "win_rate" in summary

    def test_win_rate_calculation(self):
        """Win rate computed correctly."""
        self.bb.record_trade_result({"pnl": 50})
        self.bb.record_trade_result({"pnl": -20})
        self.bb.record_trade_result({"pnl": 30})
        summary = self.bb.get_status_summary()
        assert abs(summary["win_rate"] - 0.667) < 0.01
