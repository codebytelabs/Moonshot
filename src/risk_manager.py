import numpy as np

class RiskManager:
    def __init__(self, max_risk_per_trade_pct: float = 0.01, max_positions: int = 5):
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_positions = max_positions

    def position_size_usd(self, equity_usd: float, posterior: float) -> float:
        # scale with confidence, capped
        mult = np.clip((posterior - 0.5) * 2.0, 0.2, 1.5)
        risk_pct = np.clip(self.max_risk_per_trade_pct * mult, 0.002, self.max_risk_per_trade_pct)
        return float(equity_usd * risk_pct)
