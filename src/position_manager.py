from loguru import logger
from .utils.metrics import trades_total, active_positions

class PositionManager:
    def __init__(self, exchange, mode: str = 'paper'):
        self.exchange = exchange
        self.mode = mode
        self.positions = {}

    def execute_entry(self, symbol: str, notional_usd: float, limit_price: float | None = None):
        """In paper mode: simulate fills. In live mode: place CCXT orders (implement carefully)."""
        if self.mode != 'live':
            logger.info(f"[PAPER] BUY {symbol} notional~${notional_usd:.2f} @ {limit_price}")
            trades_total.labels(exchange=self.exchange.name, symbol=symbol, side='buy', mode=self.mode).inc()
            self.positions[symbol] = {'symbol': symbol, 'notional_usd': notional_usd, 'entry_price': limit_price}
            active_positions.set(len(self.positions))
            return {'status': 'paper_filled'}

        raise NotImplementedError('Live execution is intentionally disabled in scaffold. Implement after paper trading.')
