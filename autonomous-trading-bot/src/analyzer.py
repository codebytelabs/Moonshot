"""
Analyzer Agent — Multi-Timeframe Technical Analysis.
Takes Watcher candidates, performs deep TA across 4 timeframes,
detects setup patterns, computes entry zones, and extracts ML features.
"""
import asyncio
import numpy as np
from typing import Optional
from loguru import logger

from .exchange_ccxt import ExchangeConnector
from .redis_client import RedisClient
from .supabase_client import SupabaseStore
from .metrics import signals_generated
from .watcher import _ema, _rsi, _macd_signal, _volume_spike, _obv_trend, _rate_of_change

# ── Additional TA helpers ───────────────────────────────────────────────


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Average True Range."""
    if len(closes) < period + 1:
        return 0.0
    tr = np.zeros(len(closes))
    for i in range(1, len(closes)):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    return float(np.mean(tr[-period:]))


def _bollinger_width(closes: np.ndarray, period: int = 20) -> float:
    """Bollinger Band width (normalized)."""
    if len(closes) < period:
        return 0.0
    sma = np.mean(closes[-period:])
    std = np.std(closes[-period:])
    if sma == 0:
        return 0.0
    return float((2 * std) / sma * 100)


def _stochastic_rsi(closes: np.ndarray, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> tuple[float, float]:
    """Stochastic RSI: returns (%K, %D)."""
    if len(closes) < period + smooth_k + smooth_d:
        return (50.0, 50.0)
    # Compute RSI series
    deltas = np.diff(closes)
    rsi_values = []
    for i in range(period, len(closes)):
        window = deltas[i - period:i]
        gains = np.where(window > 0, window, 0)
        losses = np.where(window < 0, -window, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
    if len(rsi_values) < period:
        return (50.0, 50.0)
    rsi_arr = np.array(rsi_values)
    # Stochastic of RSI
    stoch_k_values = []
    for i in range(period - 1, len(rsi_arr)):
        window = rsi_arr[i - period + 1:i + 1]
        low = np.min(window)
        high = np.max(window)
        if high == low:
            stoch_k_values.append(50.0)
        else:
            stoch_k_values.append((rsi_arr[i] - low) / (high - low) * 100)
    if len(stoch_k_values) < smooth_k:
        return (50.0, 50.0)
    k = np.mean(stoch_k_values[-smooth_k:])
    d = np.mean(stoch_k_values[-smooth_d:]) if len(stoch_k_values) >= smooth_d else k
    return (float(k), float(d))


def _support_resistance(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, lookback: int = 50) -> dict:
    """Simple support/resistance from recent highs and lows."""
    if len(closes) < lookback:
        lookback = len(closes)
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]
    return {
        "resistance": float(np.max(recent_highs)),
        "support": float(np.min(recent_lows)),
        "current": float(closes[-1]),
    }


# ── Setup detection ─────────────────────────────────────────────────────

def _detect_setup(features: dict) -> str:
    """Classify setup type from feature dict."""
    rsi = features.get("rsi", 50)
    macd = features.get("macd_hist", 0)
    vol_spike = features.get("volume_spike", 1)
    ema_aligned = features.get("ema_aligned", 0)
    bb_width = features.get("bollinger_width", 5)
    roc = features.get("rate_of_change", 0)

    # Breakout: high volume, EMA aligned, RSI rising but not overbought
    if vol_spike > 2.0 and ema_aligned and 50 < rsi < 75 and macd > 0:
        return "breakout"

    # Momentum: strong trend, volume confirming
    if ema_aligned and macd > 0 and roc > 2 and vol_spike > 1.3:
        return "momentum"

    # Pullback: trend intact but temporary dip
    if ema_aligned and 40 < rsi < 55 and macd > -0.001:
        return "pullback"

    # Mean reversion: oversold bounce
    if rsi < 35 and vol_spike > 1.5:
        return "mean_reversion"

    # Consolidation breakout: tight bands expanding
    if bb_width < 3 and vol_spike > 1.8:
        return "consolidation_breakout"

    return "neutral"


class AnalyzerAgent:
    """
    Deep technical analysis on Watcher candidates.
    Multi-timeframe analysis (5m, 15m, 1h, 4h), pattern detection,
    ATR-based entry zones, and ML feature extraction.
    """

    def __init__(
        self,
        exchange: ExchangeConnector,
        redis: Optional[RedisClient] = None,
        store: Optional[SupabaseStore] = None,
        timeframes: Optional[list[str]] = None,
        min_score: float = 70.0,
        top_n: int = 5,
    ):
        self.exchange = exchange
        self.redis = redis
        self.store = store
        self.timeframes = timeframes or ["5m", "15m", "1h", "4h"]
        self.min_score = min_score
        self.top_n = top_n

    async def analyze(self, candidates: list[dict]) -> list[dict]:
        """
        Analyze Watcher candidates across multiple timeframes.
        Returns top N scored setups with entry zones and features.
        """
        if not candidates:
            return []

        logger.info(f"Analyzer: Processing {len(candidates)} candidates")

        # Analyze each candidate
        semaphore = asyncio.Semaphore(3)  # limit concurrent analysis
        results = []

        async def analyze_one(candidate: dict):
            async with semaphore:
                try:
                    result = await self._analyze_symbol(candidate)
                    if result and result["ta_score"] >= self.min_score:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Analyzer: Error on {candidate['symbol']}: {e}")

        await asyncio.gather(
            *[analyze_one(c) for c in candidates],
            return_exceptions=True,
        )

        # Sort by TA score and take top N
        results.sort(key=lambda x: x["ta_score"], reverse=True)
        top = results[:self.top_n]

        # Persist
        for r in top:
            signals_generated.labels(agent="analyzer").inc()
            if self.store:
                self.store.insert_analyzer_signal(
                    symbol=r["symbol"],
                    setup_type=r["setup_type"],
                    ta_score=r["ta_score"],
                    features=r["features"],
                    entry_zone=r["entry_zone"],
                )

        logger.info(f"Analyzer: {len(top)} setups passed (min score {self.min_score})")
        return top

    async def _analyze_symbol(self, candidate: dict) -> Optional[dict]:
        """Full multi-timeframe analysis for one symbol."""
        symbol = candidate["symbol"]
        tf_features = {}

        for tf in self.timeframes:
            candles = await self._get_candles(symbol, tf)
            if not candles or len(candles) < 50:
                continue
            tf_features[tf] = self._compute_features(candles)

        if not tf_features:
            return None

        # Aggregate across timeframes (weighted: higher TFs get more weight)
        tf_weights = {"5m": 0.15, "15m": 0.25, "1h": 0.35, "4h": 0.25}
        agg_score = 0.0
        total_weight = 0.0
        combined = {}

        for tf, features in tf_features.items():
            weight = tf_weights.get(tf, 0.25)
            agg_score += features.get("tf_score", 0) * weight
            total_weight += weight
            # Merge features with tf prefix
            for k, v in features.items():
                combined[f"{tf}_{k}"] = v

        if total_weight > 0:
            agg_score /= total_weight

        # Use primary timeframe (15m) for setup detection
        primary_features = tf_features.get("15m") or tf_features.get(list(tf_features.keys())[0])
        setup_type = _detect_setup(primary_features)

        # ATR-based entry zone from 15m or 5m
        entry_zone = self._compute_entry_zone(
            tf_features.get("15m") or tf_features.get("5m", {}),
            setup_type,
        )

        # Add watcher score as feature
        combined["watcher_score"] = candidate.get("score", 0)
        combined["setup_type"] = setup_type

        return {
            "symbol": symbol,
            "ta_score": round(agg_score, 2),
            "setup_type": setup_type,
            "entry_zone": entry_zone,
            "features": combined,
        }

    async def _get_candles(self, symbol: str, timeframe: str) -> Optional[list]:
        """Get candles with Redis caching."""
        if self.redis:
            cached = await self.redis.get_ohlcv(symbol, timeframe)
            if cached:
                return cached

        candles = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=200)

        if candles and self.redis:
            ttl = {"5m": 240, "15m": 600, "1h": 1800, "4h": 7200}.get(timeframe, 300)
            await self.redis.cache_ohlcv(symbol, timeframe, candles, ttl=ttl)

        return candles

    def _compute_features(self, candles: list) -> dict:
        """Compute all TA features from OHLCV candles."""
        closes = np.array([c[4] for c in candles], dtype=float)
        highs = np.array([c[2] for c in candles], dtype=float)
        lows = np.array([c[3] for c in candles], dtype=float)
        volumes = np.array([c[5] for c in candles], dtype=float)

        rsi = _rsi(closes)
        macd = _macd_signal(closes)
        vol_spike = _volume_spike(volumes)
        obv = _obv_trend(closes, volumes)
        roc = _rate_of_change(closes)
        atr = _atr(highs, lows, closes)
        bb_width = _bollinger_width(closes)
        stoch_k, stoch_d = _stochastic_rsi(closes)

        # EMA alignment
        ema9 = _ema(closes, 9)[-1]
        ema21 = _ema(closes, 21)[-1]
        ema50 = _ema(closes, 50)[-1] if len(closes) >= 50 else ema21
        ema_aligned = 1.0 if ema9 > ema21 > ema50 else 0.0

        # Support / resistance
        sr = _support_resistance(closes, highs, lows)

        # Compute per-timeframe score (0-100)
        tf_score = 0.0
        if 40 <= rsi <= 70:
            tf_score += 12 * ((rsi - 40) / 30)
        if macd > 0:
            tf_score += min(18.0, macd * 200)
        if vol_spike > 1.5:
            tf_score += min(15.0, (vol_spike - 1) * 12)
        if obv > 0:
            tf_score += min(12.0, obv * 80)
        if roc > 0:
            tf_score += min(12.0, roc * 2.5)
        tf_score += ema_aligned * 16.0
        if stoch_k < 30 or stoch_d < 30:
            tf_score += 8.0  # oversold bounce potential
        if bb_width < 4:
            tf_score += 7.0  # tight consolidation

        return {
            "rsi": round(rsi, 2),
            "macd_hist": round(macd, 6),
            "volume_spike": round(vol_spike, 2),
            "obv_trend": round(obv, 4),
            "rate_of_change": round(roc, 2),
            "atr": round(atr, 6),
            "bollinger_width": round(bb_width, 2),
            "stoch_k": round(stoch_k, 2),
            "stoch_d": round(stoch_d, 2),
            "ema_aligned": ema_aligned,
            "ema9": round(ema9, 6),
            "ema21": round(ema21, 6),
            "ema50": round(ema50, 6),
            "support": sr["support"],
            "resistance": sr["resistance"],
            "current_price": sr["current"],
            "tf_score": round(min(100.0, tf_score), 2),
        }

    def _compute_entry_zone(self, features: dict, setup_type: str) -> dict:
        """Compute entry/stop/target zone based on ATR and setup type."""
        price = features.get("current_price", 0)
        atr = features.get("atr", 0)
        support = features.get("support", 0)

        if price == 0 or atr == 0:
            return {"entry": price, "stop_loss": price * 0.97, "take_profit": price * 1.06, "r_ratio": 2.0}

        if setup_type == "breakout":
            stop = max(price - 2 * atr, support)
            target = price + 4 * atr
        elif setup_type == "pullback":
            stop = price - 1.5 * atr
            target = price + 3 * atr
        elif setup_type == "mean_reversion":
            stop = price - 2.5 * atr
            target = price + 3 * atr
        elif setup_type == "momentum":
            stop = price - 1.5 * atr
            target = price + 5 * atr
        else:
            stop = price - 2 * atr
            target = price + 4 * atr

        risk = price - stop
        r_ratio = (target - price) / risk if risk > 0 else 2.0

        return {
            "entry": round(price, 8),
            "stop_loss": round(stop, 8),
            "take_profit": round(target, 8),
            "atr": round(atr, 8),
            "r_ratio": round(r_ratio, 2),
        }
