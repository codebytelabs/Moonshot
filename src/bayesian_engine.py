import numpy as np

class BayesianEngine:
    """Lightweight Bayesian-style scoring.

    NOTE: This is a simplified placeholder to avoid heavy MCMC in the main loop.
    You can replace `posterior()` with a full PyMC model once you have data.
    """

    def __init__(self, base_prior: float = 0.60):
        self.base_prior = base_prior

    def posterior(self, ta_score: float, context_confidence: float) -> float:
        # Convert to pseudo-likelihoods
        ta_like = np.clip(ta_score / 100.0, 0.0, 1.0)
        ctx_like = np.clip(context_confidence, 0.0, 1.0)

        # naive bayes-ish combination
        p = self.base_prior
        combined = p * (0.55 + 0.45*ta_like) * (0.60 + 0.40*ctx_like)
        return float(np.clip(combined, 0.0, 0.99))

    def should_enter(self, posterior: float, mode: str) -> bool:
        thresh = {'normal': 0.65, 'volatile': 0.75, 'safety': 0.85}.get(mode, 0.65)
        return posterior >= thresh
