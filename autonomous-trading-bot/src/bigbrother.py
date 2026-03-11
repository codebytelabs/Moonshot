"""
BigBrother Agent — Autonomous supervisor.
Manages operating mode, detects anomalies, provides LLM-powered explanations,
tracks performance, and escalates alerts.
"""
import time
from typing import Optional
from loguru import logger

from .risk_manager import RiskManager
from .bayesian_engine import BayesianDecisionEngine
from .supabase_client import SupabaseStore
from .metrics import current_drawdown, win_rate, avg_r_multiple


class BigBrotherAgent:
    """
    High-level supervisor that:
    1. Monitors portfolio health and adjusts operating mode
    2. Detects anomalies (sudden drawdown, unusual volatility)
    3. Provides LLM-powered explanations of key events
    4. Tracks rolling performance metrics
    5. Fires alerts for critical events
    """

    def __init__(
        self,
        risk_manager: RiskManager,
        decision_engine: BayesianDecisionEngine,
        store: Optional[SupabaseStore] = None,
        openrouter_client=None,
        alert_fn=None,
    ):
        self.risk = risk_manager
        self.engine = decision_engine
        self.store = store
        self.openrouter = openrouter_client
        self.alert_fn = alert_fn

        # Performance tracking
        self.trade_results: list[dict] = []
        self.current_mode = "normal"
        self.mode_change_time = time.time()
        self.events: list[dict] = []

    async def supervise(self) -> dict:
        """
        Run supervision cycle. Called after each trading loop.
        Returns mode and any events generated.
        """
        health = self.risk.check_portfolio_health()
        events = []

        # Mode management
        recommended = health.get("recommended_mode", "normal")
        if recommended != self.current_mode:
            old_mode = self.current_mode
            self.current_mode = recommended
            self.engine.set_mode(recommended)
            self.mode_change_time = time.time()

            event = {
                "type": "mode_change",
                "severity": "warning" if recommended == "safety" else "info",
                "message": f"Mode changed: {old_mode} → {recommended}",
                "details": health,
            }
            events.append(event)
            logger.warning(f"BigBrother: Mode change {old_mode} → {recommended}")

            if self.alert_fn:
                await self.alert_fn(
                    f"⚠️ Mode: {old_mode} → {recommended}\n"
                    f"Drawdown: {health['drawdown_pct']:.1%}\n"
                    f"Daily PnL: ${health['daily_pnl']:.2f}",
                    priority="high" if recommended == "safety" else "medium",
                )

        # Trading halt check
        if not health.get("can_trade", True):
            event = {
                "type": "trading_halted",
                "severity": "critical",
                "message": "Trading halted due to risk limits",
                "details": health,
            }
            events.append(event)
            if self.alert_fn:
                await self.alert_fn("🚨 TRADING HALTED — Risk limits breached", priority="critical")

        # Update Prometheus gauges
        current_drawdown.set(health.get("drawdown_pct", 0))

        # Update rolling win rate
        if self.trade_results:
            wins = sum(1 for t in self.trade_results[-50:] if t.get("pnl", 0) > 0)
            total = min(len(self.trade_results), 50)
            wr = wins / total if total > 0 else 0
            win_rate.set(wr)

            r_multiples = [t.get("r_multiple", 0) for t in self.trade_results[-50:]]
            avg_r_multiple.set(sum(r_multiples) / len(r_multiples) if r_multiples else 0)

        # Persist events
        for ev in events:
            self.events.append(ev)
            if self.store:
                self.store.insert_bigbrother_event(
                    event_type=ev["type"],
                    severity=ev["severity"],
                    message=ev["message"],
                    details=ev.get("details"),
                )

        return {
            "mode": self.current_mode,
            "health": health,
            "events": events,
        }

    def record_trade_result(self, trade: dict):
        """Record a completed trade for performance tracking."""
        self.trade_results.append(trade)

        # Update Bayesian priors
        setup_type = trade.get("setup_type", "neutral")
        profitable = trade.get("pnl", 0) > 0
        self.engine.update_prior(setup_type, profitable)

    async def explain_event(self, event: dict) -> str:
        """Use LLM to generate a human-readable explanation of a trading event."""
        if not self.openrouter:
            return event.get("message", "No explanation available")

        prompt = (
            f"Explain this trading bot event in 2-3 sentences:\n"
            f"Type: {event.get('type')}\n"
            f"Message: {event.get('message')}\n"
            f"Details: {event.get('details', {})}\n"
            f"Current mode: {self.current_mode}"
        )

        try:
            response = await self.openrouter.chat(prompt)
            return response
        except Exception as e:
            logger.error(f"BigBrother LLM explanation failed: {e}")
            return event.get("message", "Explanation unavailable")

    def get_status_summary(self) -> dict:
        """Get a summary of BigBrother state."""
        health = self.risk.check_portfolio_health()
        recent_events = self.events[-10:] if self.events else []
        total_trades = len(self.trade_results)
        wins = sum(1 for t in self.trade_results if t.get("pnl", 0) > 0)

        return {
            "mode": self.current_mode,
            "health": health,
            "total_trades": total_trades,
            "win_rate": round(wins / total_trades, 3) if total_trades > 0 else 0,
            "recent_events": recent_events,
        }
