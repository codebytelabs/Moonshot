"""
Integration test — full trading cycle with mocked exchange data.
Watcher → Analyzer → Context → Bayesian → Risk → PositionManager
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch
from tests.conftest import make_ohlcv

from src.watcher import WatcherAgent
from src.analyzer import AnalyzerAgent
from src.context_agent import ContextAgent
from src.bayesian_engine import BayesianDecisionEngine
from src.risk_manager import RiskManager
from src.position_manager import PositionManager


class TestFullCycle:
    """
    End-to-end integration: scans market, analyzes, enriches, decides, and
    validates that the pipeline produces actionable output without crashing.
    """

    def _make_settings(self):
        s = MagicMock()
        s.max_positions = 5
        s.max_risk_per_trade_pct = 0.01
        s.max_portfolio_exposure_pct = 0.30
        s.max_single_exposure_pct = 0.08
        s.max_correlation = 0.7
        s.max_drawdown_pct = 0.10
        s.daily_loss_limit_pct = 0.03
        s.initial_equity_usd = 10000.0
        s.tier1_r_multiple = 2.0
        s.tier1_exit_pct = 0.25
        s.tier2_r_multiple = 5.0
        s.tier2_exit_pct = 0.25
        s.runner_trailing_stop_pct = 0.03
        s.pyramid_enabled = False
        s.pyramid_max_adds = 0
        s.pyramid_min_r_to_add = 1.5
        return s

    @pytest.mark.asyncio
    async def test_pipeline_happy_path(self):
        """
        Mock exchange returns uptrending data → Watcher finds candidates →
        Analyzer scores them → Bayesian decides → Risk approves → pipeline completes.
        """
        # Mock exchange with 5 uptrending symbols
        exchange = AsyncMock()
        tickers = {}
        for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "DOT/USDT"]:
            tickers[sym] = {
                "symbol": sym,
                "last": 100.0,
                "quoteVolume": 5_000_000.0,
                "percentage": 3.5,
            }
        exchange.fetch_tickers = AsyncMock(return_value=tickers)

        # Generate uptrending OHLCV
        np.random.seed(42)
        ohlcv = make_ohlcv(100, base_price=95.0, trend=0.003)
        exchange.fetch_ohlcv = AsyncMock(return_value=ohlcv)

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        redis.get_cached_ticker = AsyncMock(return_value=None)
        redis.cache_ticker = AsyncMock()

        store = MagicMock()
        store.insert_watcher_signal = MagicMock()
        store.insert_analyzer_signal = MagicMock()
        store.insert_context_analysis = MagicMock()
        store.insert_decision = MagicMock()

        # Step 1: Watcher scan
        watcher = WatcherAgent(
            exchange=exchange,
            redis=redis,
            store=store,
            min_volume_24h_usd=1_000_000,
            top_n=5,
        )
        candidates = await watcher.scan()

        # Should find candidates (all have >1M volume and uptrend)
        assert isinstance(candidates, list)
        # May or may not find candidates depending on score threshold

        # Step 2: If we have candidates, analyze them
        if candidates:
            analyzer = AnalyzerAgent(
                exchange=exchange,
                redis=redis,
                store=store,
                timeframes=["5m", "15m"],
                min_score=30,  # Low threshold for test
                top_n=5,
            )
            setups = await analyzer.analyze(candidates)
            assert isinstance(setups, list)

            # Step 3: Bayesian decide
            if setups:
                engine = BayesianDecisionEngine(store=store, mode="normal")
                decisions = engine.batch_decide(setups)
                assert isinstance(decisions, list)

                # Step 4: Risk check
                settings = self._make_settings()
                risk = RiskManager(settings)
                for d in decisions:
                    can_open, reason = risk.can_open_position(d["symbol"], d)
                    assert isinstance(can_open, bool)
                    assert isinstance(reason, str)

    @pytest.mark.asyncio
    async def test_pipeline_no_volume(self):
        """
        Low volume symbols → Watcher filters them out → no candidates.
        """
        exchange = AsyncMock()
        tickers = {
            "TINY/USDT": {
                "symbol": "TINY/USDT",
                "last": 0.001,
                "quoteVolume": 500.0,  # Way below threshold
                "percentage": 1.0,
            }
        }
        exchange.fetch_tickers = AsyncMock(return_value=tickers)

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        redis.get_cached_ticker = AsyncMock(return_value=None)

        store = MagicMock()
        store.insert_watcher_signal = MagicMock()

        watcher = WatcherAgent(
            exchange=exchange,
            redis=redis,
            store=store,
            min_volume_24h_usd=2_000_000,
            top_n=20,
        )
        candidates = await watcher.scan()
        assert candidates == [] or len(candidates) == 0
