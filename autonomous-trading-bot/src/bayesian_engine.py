"""
Bayesian Decision Engine.
Uses Bayesian inference with setup-specific priors to combine
TA score, ML features, and market context into a posterior probability.
Mode-based thresholds determine the final action (enter/skip/reject).
"""
import math
from typing import Optional
from loguru import logger

from .supabase_client import SupabaseStore
from .metrics import decisions_made


# ── Prior probabilities per setup type ──────────────────────────────────
SETUP_PRIORS = {
    "breakout": 0.45,
    "momentum": 0.50,
    "pullback": 0.40,
    "mean_reversion": 0.35,
    "consolidation_breakout": 0.40,
    "neutral": 0.25,
}

# ── Mode thresholds ─────────────────────────────────────────────────────
MODE_THRESHOLDS = {
    "normal": 0.65,
    "volatile": 0.75,
    "safety": 0.85,
}


def _sigmoid(x: float, midpoint: float = 50, steepness: float = 0.1) -> float:
    """Sigmoid mapping: maps score (0-100) to probability (0-1)."""
    try:
        return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
    except OverflowError:
        return 0.0 if x < midpoint else 1.0


def _sentiment_likelihood(context: dict) -> float:
    """Convert context sentiment to a likelihood value."""
    sentiment = context.get("sentiment", "neutral")
    confidence = context.get("confidence", 0.0)
    narrative = context.get("narrative_strength", 0.0)

    base = {"bullish": 0.75, "bearish": 0.20, "neutral": 0.45}.get(sentiment, 0.45)

    # Adjust by confidence and narrative strength
    adjusted = base + (confidence - 0.5) * 0.2 + (narrative - 0.5) * 0.15

    return max(0.05, min(0.95, adjusted))


def _risk_penalty(context: dict) -> float:
    """Compute a risk penalty (0.0-0.3) based on identified risks."""
    risks = context.get("risks", [])
    n_risks = len(risks)
    if n_risks == 0:
        return 0.0
    if n_risks == 1:
        return 0.05
    if n_risks == 2:
        return 0.10
    return min(0.30, n_risks * 0.06)


class BayesianDecisionEngine:
    """
    Bayesian inference for trading decisions.

    P(success | data) ∝ P(data | success) × P(success)

    Where:
    - P(success) = setup-specific prior (updated online)
    - P(data | success) = product of likelihood factors:
      - TA score likelihood (sigmoid-mapped)
      - Context sentiment likelihood
      - Volume confirmation likelihood
    """

    def __init__(
        self,
        store: Optional[SupabaseStore] = None,
        mode: str = "normal",
    ):
        self.store = store
        self.mode = mode
        self.priors = dict(SETUP_PRIORS)  # mutable copy for online updating
        self._history: list[dict] = []  # track decisions for prior updating

    def set_mode(self, mode: str):
        """Change operating mode (normal, volatile, safety)."""
        if mode in MODE_THRESHOLDS:
            self.mode = mode
            logger.info(f"Bayesian engine mode set to: {mode} (threshold: {MODE_THRESHOLDS[mode]})")

    def decide(self, setup: dict) -> dict:
        """
        Make a trading decision for a given setup.

        Args:
            setup: Dict with keys: symbol, ta_score, setup_type, features, context, entry_zone

        Returns:
            Dict with: action (enter/skip/reject), posterior, reasoning
        """
        symbol = setup.get("symbol", "?")
        ta_score = setup.get("ta_score", 0)
        setup_type = setup.get("setup_type", "neutral")
        context = setup.get("context", {})
        features = setup.get("features", {})
        entry_zone = setup.get("entry_zone", {})

        # 1. Prior
        prior = self.priors.get(setup_type, SETUP_PRIORS["neutral"])

        # 2. Likelihood factors
        # TA score → probability via sigmoid (adjusted for better mapping)
        # TA scores 70-90 should map to likelihoods 0.60-0.85
        ta_likelihood = _sigmoid(ta_score, midpoint=65, steepness=0.08)

        # Context sentiment → likelihood
        context_likelihood = _sentiment_likelihood(context)

        # Volume confirmation
        vol_spike = features.get("15m_volume_spike", features.get("volume_spike", 1.0))
        if isinstance(vol_spike, (int, float)):
            vol_likelihood = _sigmoid(vol_spike * 50, midpoint=70, steepness=0.05)
        else:
            vol_likelihood = 0.5

        # R:R ratio factor
        r_ratio = entry_zone.get("r_ratio", 2.0)
        rr_factor = min(1.0, 0.5 + (r_ratio / 6.0))  # ranges 0.5-1.0

        # 3. Posterior (simplified Bayes — product of likelihoods × prior)
        combined_likelihood = ta_likelihood * context_likelihood * vol_likelihood * rr_factor
        posterior = prior * combined_likelihood

        # Normalize to 0-1 range with adjusted factor
        # For good setups (TA>70, positive sentiment, volume), this should produce 0.50-0.80
        # Increased normalization factor to 6.5 for proper calibration
        posterior = min(0.99, posterior * 6.5)

        # Apply risk penalty (capped at 0.30)
        penalty = _risk_penalty(context)
        posterior = max(0.0, posterior - penalty)

        # 4. Decision based on threshold
        threshold = MODE_THRESHOLDS.get(self.mode, 0.65)
        if posterior >= threshold:
            action = "enter"
        elif posterior >= threshold * 0.7:
            action = "skip"  # close but not enough
        else:
            action = "reject"

        reasoning = {
            "prior": round(prior, 3),
            "ta_likelihood": round(ta_likelihood, 3),
            "context_likelihood": round(context_likelihood, 3),
            "vol_likelihood": round(vol_likelihood, 3),
            "rr_factor": round(rr_factor, 3),
            "risk_penalty": round(penalty, 3),
            "threshold": round(threshold, 3),
            "mode": self.mode,
            "ta_score": ta_score,
            "sentiment": context.get("sentiment", "neutral"),
        }

        # Track decision
        decisions_made.labels(outcome=action).inc()
        logger.info(
            f"Bayesian [{symbol}]: action={action} posterior={posterior:.3f} "
            f"threshold={threshold:.3f} setup={setup_type} mode={self.mode}"
        )

        # Persist
        if self.store:
            self.store.insert_decision(
                symbol=symbol,
                posterior=round(posterior, 4),
                action=action,
                setup_type=setup_type,
                mode=self.mode,
                reasoning=reasoning,
            )

        result = {
            "symbol": symbol,
            "action": action,
            "posterior": round(posterior, 4),
            "setup_type": setup_type,
            "entry_zone": entry_zone,
            "reasoning": reasoning,
        }

        self._history.append(result)
        return result

    def batch_decide(self, setups: list[dict]) -> list[dict]:
        """Decide on multiple setups, return only 'enter' actions sorted by posterior."""
        decisions = [self.decide(s) for s in setups]
        enters = [d for d in decisions if d["action"] == "enter"]
        enters.sort(key=lambda x: x["posterior"], reverse=True)
        logger.info(f"Bayesian batch: {len(enters)}/{len(decisions)} setups approved")
        return enters

    def update_prior(self, setup_type: str, was_profitable: bool):
        """Online prior update after trade outcome (simple exponential smoothing)."""
        if setup_type not in self.priors:
            return
        alpha = 0.05  # learning rate
        outcome = 1.0 if was_profitable else 0.0
        old = self.priors[setup_type]
        self.priors[setup_type] = old + alpha * (outcome - old)
        logger.debug(
            f"Prior updated [{setup_type}]: {old:.3f} → {self.priors[setup_type]:.3f} "
            f"(profitable={was_profitable})"
        )
