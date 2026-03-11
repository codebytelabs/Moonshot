"""
Unit tests for Watcher Agent — TA helper functions.
"""
import numpy as np
from src.watcher import _ema, _rsi, _macd_signal, _volume_spike, _obv_trend, _rate_of_change


class TestEMA:
    def test_single_element(self):
        data = np.array([100.0])
        result = _ema(data, 14)
        assert result[0] == 100.0

    def test_constant_data(self):
        data = np.ones(50) * 42.0
        result = _ema(data, 14)
        np.testing.assert_allclose(result, 42.0, atol=1e-10)

    def test_increasing_data(self):
        data = np.arange(1.0, 51.0)
        result = _ema(data, 10)
        # EMA should lag behind but trend upward
        assert result[-1] > result[0]
        assert result[-1] < data[-1]  # EMA lags price

    def test_ema_length_matches_input(self):
        data = np.arange(1.0, 101.0)
        result = _ema(data, 20)
        assert len(result) == len(data)


class TestRSI:
    def test_overbought(self):
        """Strong uptrend → RSI > 70."""
        closes = np.array([50 + i * 0.5 for i in range(30)])
        rsi = _rsi(closes, 14)
        assert rsi > 70

    def test_oversold(self):
        """Strong downtrend → RSI < 30."""
        closes = np.array([50 - i * 0.5 for i in range(30)])
        rsi = _rsi(closes, 14)
        assert rsi < 30

    def test_range_bounds(self):
        """RSI should always be between 0 and 100."""
        np.random.seed(42)
        closes = np.cumsum(np.random.normal(0, 1, 100)) + 100
        rsi = _rsi(closes, 14)
        assert 0 <= rsi <= 100

    def test_short_data_returns_50(self):
        """Insufficient data → default RSI 50."""
        closes = np.array([100.0, 101.0])
        rsi = _rsi(closes, 14)
        assert rsi == 50.0


class TestMACDSignal:
    def test_uptrend_positive(self):
        """Strong uptrend → positive MACD signal."""
        closes = np.array([100 + i * 0.3 for i in range(50)])
        signal = _macd_signal(closes)
        assert signal > 0

    def test_downtrend_negative(self):
        """Strong downtrend → negative MACD signal."""
        closes = np.array([100 - i * 0.3 for i in range(50)])
        signal = _macd_signal(closes)
        assert signal < 0


class TestVolumeSpike:
    def test_no_spike(self):
        """Flat volume → ratio ~1.0."""
        volumes = np.ones(30) * 1000
        result = _volume_spike(volumes)
        assert 0.9 < result < 1.1

    def test_spike_detected(self):
        """Last candle volume 5x average → spike > 1.5."""
        volumes = np.ones(30) * 1000
        volumes[-1] = 5000
        result = _volume_spike(volumes)
        assert result > 1.5


class TestOBVTrend:
    def test_positive_obv(self):
        """Uptrend with increasing volume → positive OBV trend."""
        np.random.seed(42)
        closes = np.array([100 + i * 0.2 for i in range(30)])
        volumes = np.random.uniform(1000, 5000, 30)
        result = _obv_trend(closes, volumes)
        assert result > 0

    def test_returns_bounded(self):
        """OBV ratio should be reasonably bounded."""
        np.random.seed(42)
        closes = np.cumsum(np.random.normal(0, 0.5, 50)) + 100
        volumes = np.random.uniform(100, 10000, 50)
        result = _obv_trend(closes, volumes)
        assert -10 < result < 10


class TestRateOfChange:
    def test_positive_roc(self):
        """Price increase → positive RoC."""
        closes = np.array([100, 105, 110, 115, 120])
        roc = _rate_of_change(closes, 3)
        assert roc > 0

    def test_negative_roc(self):
        """Price decrease → negative RoC."""
        closes = np.array([120, 115, 110, 105, 100])
        roc = _rate_of_change(closes, 3)
        assert roc < 0


class TestEMAAlignment:
    """Test EMA alignment logic (inline in _score_symbol)."""

    def test_aligned_emas(self):
        """EMA9 > EMA21 > EMA50 in uptrend."""
        closes = np.array([100 + i for i in range(60)], dtype=float)
        ema9 = _ema(closes, 9)[-1]
        ema21 = _ema(closes, 21)[-1]
        ema50 = _ema(closes, 50)[-1]
        assert ema9 > ema21 > ema50

    def test_not_aligned_emas(self):
        """Downtrend → EMA9 < EMA21 < EMA50."""
        closes = np.array([160 - i for i in range(60)], dtype=float)
        ema9 = _ema(closes, 9)[-1]
        ema21 = _ema(closes, 21)[-1]
        ema50 = _ema(closes, 50)[-1]
        assert ema9 < ema21 < ema50
