"""
RL Exit Optimizer — Reinforcement Learning placeholder.
Defines the observation/action space and interface for future RL-based exit optimization.
Falls back to rule-based exits (via PositionManager) until enough training data exists.
"""
from typing import Optional
from loguru import logger


class RLExitOptimizer:
    """
    Placeholder for RL-based exit optimization.
    Currently delegates to rule-based exits. Will use learned policy
    once sufficient trade data (>500 closed positions) is collected.

    Observation space (when implemented):
    - Current R-multiple
    - Time in position (normalized)
    - Current RSI
    - Volume ratio
    - Unrealized PnL %
    - ATR ratio (current / entry ATR)
    - Drawdown from position peak
    - Number of tiers already exited

    Action space:
    - 0: Hold
    - 1: Exit 25%
    - 2: Exit 50%
    - 3: Exit 100%
    - 4: Tighten trailing stop to 1%
    - 5: Widen trailing stop to 5%
    """

    def __init__(self, min_trades_for_rl: int = 500):
        self.min_trades = min_trades_for_rl
        self.total_trades = 0
        self.model = None  # placeholder for stable-baselines3 model
        self.is_trained = False

    def get_action(self, observation: dict) -> int:
        """
        Get exit action for a position.
        Falls back to rule-based (action=0 hold) if RL not trained.
        """
        if not self.is_trained:
            return 0  # Hold — let PositionManager handle tier exits

        # Future: self.model.predict(obs_vector)
        return 0

    def should_use_rl(self) -> bool:
        """Whether RL model is trained and ready."""
        return self.is_trained and self.total_trades >= self.min_trades

    def record_outcome(self, observation: dict, action: int, reward: float, next_observation: dict):
        """Record a transition for future training."""
        self.total_trades += 1
        # Future: add to replay buffer
        if self.total_trades % 100 == 0:
            logger.info(f"RL buffer: {self.total_trades} transitions collected (need {self.min_trades} to train)")

    def train(self):
        """Train or update the RL model. Placeholder."""
        if self.total_trades < self.min_trades:
            logger.info(f"RL: Not enough data to train ({self.total_trades}/{self.min_trades})")
            return
        logger.info("RL: Training would happen here (stable-baselines3 PPO)")
        # Future: train with collected data
        # self.model = PPO("MlpPolicy", env, ...)
        # self.is_trained = True
