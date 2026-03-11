"""
Shared test fixtures and mocks for the Moonshot Trading Bot test suite.
"""
import os
import sys
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fake Settings (matches real config.Settings field names) ──────────
@pytest.fixture
def settings():
    """Create a fake Settings object matching real field names."""
    s = MagicMock()
    s.mode = "paper"
    s.exchange_name = "gateio"
    s.gateio_api_key = "test_key"
    s.gateio_api_secret = "test_secret"
    s.binance_api_key = ""
    s.binance_api_secret = ""

    # Risk fields (exact names from config.py)
    s.initial_equity_usd = 10000.0
    s.max_positions = 5
    s.max_risk_per_trade_pct = 0.01
    s.max_portfolio_exposure_pct = 0.30
    s.max_single_exposure_pct = 0.08
    s.max_correlation = 0.7
    s.max_drawdown_pct = 0.10
    s.daily_loss_limit_pct = 0.03

    # Tier exits
    s.tier1_r_multiple = 2.0
    s.tier1_exit_pct = 0.25
    s.tier2_r_multiple = 5.0
    s.tier2_exit_pct = 0.25
    s.runner_trailing_stop_pct = 0.03

    # Pyramid
    s.pyramid_enabled = True
    s.pyramid_max_adds = 2
    s.pyramid_min_r_to_add = 1.5

    # Watcher / Analyzer
    s.cycle_interval_seconds = 60
    s.watcher_min_volume_24h_usd = 2_000_000
    s.watcher_top_n = 20
    s.analyzer_timeframes = ["5m", "15m", "1h", "4h"]
    s.analyzer_min_score = 0.5
    s.analyzer_top_n = 10
    s.quote_currency = "USDT"

    # LLM / External
    s.redis_url = "redis://localhost:6379/0"
    s.redis_password = None
    s.supabase_url = "https://fake.supabase.co"
    s.supabase_anon_key = "fake_key"
    s.openrouter_api_key = "test_or_key"
    s.openrouter_base_url = "https://openrouter.ai/api/v1"
    s.openrouter_primary_model = "deepseek/deepseek-r1-0528:free"
    s.openrouter_secondary_model = "deepseek/deepseek-r1-0528:free"
    s.perplexity_api_key = "test_pplx_key"
    s.perplexity_base_url = "https://api.perplexity.ai"
    s.perplexity_model = "sonar"
    s.perplexity_timeout = 30
    s.perplexity_max_retries = 3
    s.perplexity_retry_delay = 1
    s.discord_webhook = None
    s.telegram_bot_token = None
    s.telegram_chat_id = None
    return s


# ── Mock Exchange ──────────────────────────────────────────────────────
@pytest.fixture
def mock_exchange():
    """Create a mock ExchangeConnector."""
    ex = AsyncMock()
    ex.name = "gateio"
    ex.exchange = MagicMock()
    ex.exchange.id = "gateio"
    return ex


# ── Mock Redis ─────────────────────────────────────────────────────────
@pytest.fixture
def mock_redis():
    """Create a mock RedisClient."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.get_cached_ticker = AsyncMock(return_value=None)
    r.cache_ticker = AsyncMock()
    return r


# ── Mock Supabase Store ───────────────────────────────────────────────
@pytest.fixture
def mock_store():
    """Create a mock SupabaseStore."""
    store = MagicMock()
    store.insert_watcher_signal = MagicMock()
    store.insert_analyzer_signal = MagicMock()
    store.insert_context_analysis = MagicMock()
    store.insert_decision = MagicMock()
    store.upsert_position = MagicMock()
    store.insert_trade = MagicMock()
    store.insert_bigbrother_event = MagicMock()
    store.get_recent_trades = MagicMock(return_value=[])
    store.get_performance_history = MagicMock(return_value=[])
    return store


# ── OHLCV Helper ──────────────────────────────────────────────────────
def make_ohlcv(n: int = 100, base_price: float = 50000.0, trend: float = 0.001):
    """Generate synthetic OHLCV data as a list of [ts, O, H, L, C, V]."""
    data = []
    price = base_price
    now = 1700000000000
    for i in range(n):
        open_p = price
        change = np.random.normal(trend, 0.005)
        close_p = open_p * (1 + change)
        high = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.003)))
        low = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.003)))
        volume = np.random.uniform(100, 10000)
        data.append([now + i * 60000, open_p, high, low, close_p, volume])
        price = close_p
    return data
