"""
Watcher Agent — Market Scanner.
Scans 150+ USDT pairs on Gate.io, scores them using TA indicators,
filters by volume and momentum, and emits top candidates.
"""
import asyncio
import numpy as np
from typing import Optional
from loguru import logger

from .exchange_ccxt import ExchangeConnector
from .redis_client import RedisClient
from .supabase_client import SupabaseStore
from .metrics import signals_generated

# ── TA helpers (numpy-based, no heavy deps) ─────────────────────────────


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    alpha = 2.0 / (period + 1)
    ema = np.zeros_like(data, dtype=float)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    """Latest RSI value."""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _macd_signal(closes: np.ndarray) -> float:
    """MACD histogram value (positive = bullish crossover)."""
    if len(closes) < 26:
        return 0.0
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    return float(macd_line[-1] - signal_line[-1])


def _volume_spike(volumes: np.ndarray, lookback: int = 20) -> float:
    """Current volume relative to average (>1 means above average)."""
    if len(volumes) < lookback + 1:
        return 1.0
    avg_vol = np.mean(volumes[-lookback - 1:-1])
    if avg_vol == 0:
        return 1.0
    return float(volumes[-1] / avg_vol)


def _obv_trend(closes: np.ndarray, volumes: np.ndarray, lookback: int = 10) -> float:
    """OBV slope over lookback period. Positive = accumulation."""
    if len(closes) < lookback + 1:
        return 0.0
    obv = np.zeros(len(closes))
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - volumes[i]
        else:
            obv[i] = obv[i - 1]
    # Slope of last N OBV values (normalized)
    recent = obv[-lookback:]
    x = np.arange(lookback)
    slope = np.polyfit(x, recent, 1)[0]
    # Normalize by average volume
    avg_vol = np.mean(volumes[-lookback:])
    return float(slope / avg_vol) if avg_vol > 0 else 0.0


def _rate_of_change(closes: np.ndarray, period: int = 12) -> float:
    """Rate of change over period (percentage)."""
    if len(closes) < period + 1:
        return 0.0
    return float((closes[-1] - closes[-period - 1]) / closes[-period - 1] * 100)


class WatcherAgent:
    """
    Scans the exchange for tradeable opportunities.
    Fetches 5m OHLCV data, computes TA indicators, scores each pair,
    and returns the top N candidates.
    """

    def __init__(
        self,
        exchange: ExchangeConnector,
        redis: Optional[RedisClient] = None,
        store: Optional[SupabaseStore] = None,
        min_volume_24h_usd: float = 2_000_000.0,
        top_n: int = 20,
    ):
        self.exchange = exchange
        self.redis = redis
        self.store = store
        self.min_volume_24h_usd = min_volume_24h_usd
        self.top_n = top_n

    async def scan(self) -> list[dict]:
        """
        Full scan cycle:
        1. Fetch all USDT tickers
        2. Filter by volume
        3. Fetch 5m candles for qualifying pairs
        4. Score each pair
        5. Return top N candidates sorted by score
        """
        logger.info("Watcher scan started")

        # Step 1: Fetch all tickers
        try:
            tickers = await self.exchange.fetch_tickers()
        except Exception as e:
            logger.error(f"Watcher: Failed to fetch tickers: {e}")
            return []

        # Step 2: Filter USDT pairs with minimum volume
        usdt_pairs = []
        for symbol, ticker in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            quote_vol = ticker.get("quoteVolume") or 0
            if quote_vol >= self.min_volume_24h_usd:
                usdt_pairs.append((symbol, ticker))

        logger.info(f"Watcher: {len(usdt_pairs)} USDT pairs above ${self.min_volume_24h_usd/1e6:.0f}M volume")

        if not usdt_pairs:
            return []

        # Step 3-4: Score each pair (batch with rate limiting)
        scored = []
        semaphore = asyncio.Semaphore(5)  # max 5 concurrent OHLCV fetches

        async def score_pair(sym: str, tick: dict):
            async with semaphore:
                try:
                    result = await self._score_symbol(sym, tick)
                    if result:
                        scored.append(result)
                except Exception as e:
                    logger.debug(f"Watcher: Error scoring {sym}: {e}")

        await asyncio.gather(
            *[score_pair(sym, tick) for sym, tick in usdt_pairs],
            return_exceptions=True,
        )

        # Step 5: Sort by score, return top N
        scored.sort(key=lambda x: x["score"], reverse=True)
        candidates = scored[:self.top_n]

        # Persist and cache
        for c in candidates:
            signals_generated.labels(agent="watcher").inc()
            if self.store:
                self.store.insert_watcher_signal(
                    symbol=c["symbol"],
                    score=c["score"],
                    features=c["features"],
                )
            if self.redis:
                await self.redis.set(f"watcher:{c['symbol']}", c, ttl=300)

        logger.info(f"Watcher scan complete: {len(candidates)} candidates emitted")
        return candidates

    async def _score_symbol(self, symbol: str, ticker: dict) -> Optional[dict]:
        """Fetch OHLCV and compute composite score for one symbol."""
        # Try Redis cache first
        if self.redis:
            cached = await self.redis.get_ohlcv(symbol, "5m")
            if cached:
                candles = cached
            else:
                candles = await self.exchange.fetch_ohlcv(symbol, "5m", limit=100)
                await self.redis.cache_ohlcv(symbol, "5m", candles, ttl=240)
        else:
            candles = await self.exchange.fetch_ohlcv(symbol, "5m", limit=100)

        if not candles or len(candles) < 50:
            return None

        # Extract arrays
        closes = np.array([c[4] for c in candles], dtype=float)
        volumes = np.array([c[5] for c in candles], dtype=float)

        # Compute features
        rsi = _rsi(closes)
        macd = _macd_signal(closes)
        vol_spike = _volume_spike(volumes)
        obv = _obv_trend(closes, volumes)
        roc = _rate_of_change(closes)

        # EMA alignment
        ema9 = _ema(closes, 9)[-1]
        ema21 = _ema(closes, 21)[-1]
        ema50 = _ema(closes, 50)[-1] if len(closes) >= 50 else ema21
        ema_aligned = 1.0 if ema9 > ema21 > ema50 else 0.0

        # Composite score (0-100)
        score = 0.0

        # RSI: sweet spot 40-60 neutral, >60 momentum
        if 40 <= rsi <= 70:
            score += 15 * ((rsi - 40) / 30)
        elif rsi > 70:
            score += 10  # overbought but might still run

        # MACD bullish crossover
        if macd > 0:
            score += min(20.0, macd * 200)

        # Volume spike
        if vol_spike > 1.5:
            score += min(20.0, (vol_spike - 1) * 15)

        # OBV accumulation
        if obv > 0:
            score += min(15.0, obv * 100)

        # Rate of change
        if roc > 0:
            score += min(15.0, roc * 3)

        # EMA alignment bonus
        score += ema_aligned * 15.0

        # Price near ticker
        current_price = ticker.get("last") or closes[-1]
        change_24h = ticker.get("percentage") or 0

        features = {
            "rsi": round(rsi, 2),
            "macd_hist": round(macd, 6),
            "volume_spike": round(vol_spike, 2),
            "obv_trend": round(obv, 4),
            "rate_of_change": round(roc, 2),
            "ema_aligned": ema_aligned,
            "price": current_price,
            "change_24h": round(change_24h, 2),
            "volume_24h_usd": ticker.get("quoteVolume", 0),
        }

        return {
            "symbol": symbol,
            "score": round(min(100.0, score), 2),
            "features": features,
        }
