"""
Unit tests for Bayesian Decision Engine.
"""
import math
from unittest.mock import MagicMock
from src.bayesian_engine import (
    BayesianDecisionEngine,
    _sigmoid,
    _sentiment_likelihood,
    SETUP_PRIORS,
    MODE_THRESHOLDS,
)


class TestSigmoid:
    def test_midpoint_returns_half(self):
        """At midpoint, sigmoid should return ~0.5."""
        assert abs(_sigmoid(50, midpoint=50) - 0.5) < 0.01

    def test_high_input(self):
        """High input → close to 1.0."""
        result = _sigmoid(90, midpoint=50)
        assert result > 0.95

    def test_low_input(self):
        """Low input → close to 0.0."""
        result = _sigmoid(10, midpoint=50)
        assert result < 0.05

    def test_overflow_protection(self):
        """Very extreme values should not raise OverflowError."""
        assert _sigmoid(10000, midpoint=50) == 1.0
        assert _sigmoid(-10000, midpoint=50) == 0.0


class TestSentimentLikelihood:
    def test_bullish(self):
        ctx = {"sentiment": "bullish", "confidence": 0.8, "narrative_strength": 0.7}
        result = _sentiment_likelihood(ctx)
        assert result > 0.5

    def test_bearish(self):
        ctx = {"sentiment": "bearish", "confidence": 0.8, "narrative_strength": 0.7}
        result = _sentiment_likelihood(ctx)
        assert result < 0.5

    def test_neutral_returns_around_half(self):
        ctx = {"sentiment": "neutral", "confidence": 0.5, "narrative_strength": 0.5}
        result = _sentiment_likelihood(ctx)
        assert 0.2 < result < 0.8

    def test_empty_context(self):
        """Empty context → returns a valid probability."""
        result = _sentiment_likelihood({})
        assert 0.0 <= result <= 1.0


class TestPriorsAndThresholds:
    def test_all_priors_valid(self):
        for setup, prior in SETUP_PRIORS.items():
            assert 0 < prior < 1, f"Prior for {setup} is out of range: {prior}"

    def test_thresholds_ordered(self):
        assert MODE_THRESHOLDS["normal"] < MODE_THRESHOLDS["volatile"]
        assert MODE_THRESHOLDS["volatile"] < MODE_THRESHOLDS["safety"]


class TestBayesianEngine:
    def setup_method(self):
        self.store = MagicMock()
        self.engine = BayesianDecisionEngine(store=self.store, mode="normal")

    def test_decide_returns_valid_action(self):
        """High TA + bullish context → returns a valid action."""
        setup = {
            "symbol": "BTC/USDT",
            "ta_score": 85,
            "setup_type": "momentum",
            "features": {"volume_spike": 3.0},  # high volume spike through features
            "entry_zone": {"entry": 50000, "stop_loss": 49000, "take_profit": 55000, "r_ratio": 3.0},
            "context": {"sentiment": "bullish", "confidence": 0.9, "narrative_strength": 0.9},
        }
        result = self.engine.decide(setup)
        assert result["action"] in ("enter", "skip", "reject")
        assert "posterior" in result
        assert 0 <= result["posterior"] <= 1.0

    def test_decide_skip(self):
        """Low TA + neutral context → skip or reject."""
        setup = {
            "symbol": "DOGE/USDT",
            "ta_score": 30,
            "setup_type": "neutral",
            "features": {"volume_spike": 0.5},
            "entry_zone": {"entry": 0.10, "stop_loss": 0.09, "take_profit": 0.12, "r_ratio": 1.0},
            "context": {"sentiment": "neutral", "confidence": 0.3, "narrative_strength": 0.2},
        }
        result = self.engine.decide(setup)
        assert result["action"] in ("skip", "reject")
        assert result["posterior"] < MODE_THRESHOLDS["normal"]

    def test_mode_safety_higher_threshold(self):
        """Safety mode requires higher posterior."""
        self.engine.set_mode("safety")
        setup = {
            "symbol": "ETH/USDT",
            "ta_score": 70,
            "setup_type": "breakout",
            "features": {"volume_spike": 1.5},
            "entry_zone": {"entry": 3000, "stop_loss": 2900, "take_profit": 3500, "r_ratio": 2.0},
            "context": {"sentiment": "neutral", "confidence": 0.5, "narrative_strength": 0.5},
        }
        result = self.engine.decide(setup)
        # Moderate signal in safety mode → likely skip/reject
        assert result["action"] in ("skip", "reject")

    def test_update_prior(self):
        """Prior update should shift after profitable trade."""
        old_prior = self.engine.priors["breakout"]
        self.engine.update_prior("breakout", was_profitable=True)
        new_prior = self.engine.priors["breakout"]
        # Profitable trade should increase prior (alpha=0.05 smoothing)
        assert new_prior > old_prior

    def test_update_prior_loss(self):
        """Losing trade should decrease prior."""
        old_prior = self.engine.priors["momentum"]
        self.engine.update_prior("momentum", was_profitable=False)
        new_prior = self.engine.priors["momentum"]
        assert new_prior < old_prior

    def test_batch_decide(self):
        """Batch should only return 'enter' decisions."""
        setups = [
            {
                "symbol": f"TOKEN{i}/USDT",
                "ta_score": 90 + i,
                "setup_type": "momentum",
                "features": {"volume_spike": 4.0},
                "entry_zone": {"entry": 100, "stop_loss": 95, "take_profit": 120, "r_ratio": 4.0},
                "context": {"sentiment": "bullish", "confidence": 0.9, "narrative_strength": 0.9},
            }
            for i in range(3)
        ]
        results = self.engine.batch_decide(setups)
        # All results (if any) should be "enter"
        for r in results:
            assert r["action"] == "enter"

    def test_set_mode(self):
        """Mode should change when set_mode is called."""
        self.engine.set_mode("volatile")
        assert self.engine.mode == "volatile"
        self.engine.set_mode("safety")
        assert self.engine.mode == "safety"
