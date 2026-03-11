from loguru import logger

class BigBrotherAgent:
    """Supervisor that enforces guardrails and can request human review.

    This scaffold keeps it simple: evaluate drawdown / error rates and switch mode.
    """

    def __init__(self, max_drawdown_pct: float = 0.10):
        self.max_drawdown_pct = max_drawdown_pct

    def decide_mode(self, metrics: dict) -> str:
        dd = metrics.get('current_drawdown_pct', 0.0)
        if dd >= self.max_drawdown_pct:
            logger.warning(f"Drawdown {dd:.2%} exceeded limit {self.max_drawdown_pct:.2%}. Safety mode.")
            return 'safety'
        return 'normal'
