# Placeholder RL optimizer module.
#
# You will train PPO using Stable-Baselines3 on your own trade episodes.
# This file exists to define the interface used by the PositionManager.

class RLExitOptimizer:
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.ready = False

    def load(self):
        # Load Stable-Baselines3 model here
        self.ready = False

    def recommend(self, position_state: dict) -> str:
        # Return one of: HOLD, TP_PARTIAL, EXIT, DCA
        return 'HOLD'
