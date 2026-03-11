"""
Central configuration using Pydantic Settings.
Reads all environment variables from .env and provides typed, validated config.
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

# Resolve .env path: autonomous-trading-bot/src/config.py → ../../.env
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """All configuration for the Moonshot trading bot."""

    # ── Exchange (Gate.io primary) ───────────────────────────────────────
    exchange_name: str = Field(default="gateio", description="Primary exchange identifier")
    gateio_api_key: Optional[str] = Field(default=None, alias="GATEIO_API_KEY")
    gateio_api_secret: Optional[str] = Field(default=None, alias="GATEIO_API_SECRET")

    # Fallback exchanges
    binance_api_key: Optional[str] = Field(default=None, alias="BINANCE_API_KEY")
    binance_api_secret: Optional[str] = Field(default=None, alias="BINANCE_API_SECRET")
    kucoin_api_key: Optional[str] = Field(default=None, alias="KUCOIN_API_KEY")
    kucoin_api_secret: Optional[str] = Field(default=None, alias="KUCOIN_API_SECRET")
    kucoin_passphrase: Optional[str] = Field(default=None, alias="KUCOIN_PASSPHRASE")

    # ── Demo / Testnet Exchanges ────────────────────────────────────────
    binance_demo_api_key: Optional[str] = Field(default=None, alias="BINANCE_DEMO_API_KEY")
    binance_demo_api_secret: Optional[str] = Field(default=None, alias="BINANCE_DEMO_API_SECRET")
    binance_demo_url: str = Field(default="https://demo-api.binance.com", alias="BINANCE_DEMO_URL")

    gateio_testnet_api_key: Optional[str] = Field(default=None, alias="GATEIO_TESTNET_API_KEY")
    gateio_testnet_secret_key: Optional[str] = Field(default=None, alias="GATEIO_TESTNET_SECRET_KEY")
    gateio_testnet_url: str = Field(default="https://api-testnet.gateapi.io/api/v4", alias="GATEIO_TESTNET_URL_Endpoint")

    exchange_mode: str = Field(default="paper", alias="EXCHANGE_MODE", description="paper | demo | live")

    # ── LLM / AI ────────────────────────────────────────────────────────
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    openrouter_secondary_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_Secondary_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_API_BASE_URL")
    openrouter_primary_model: str = Field(default="google/gemini-3-flash-preview", alias="OPENROUTER_PRIMARY_MODEL")
    openrouter_secondary_model: str = Field(default="deepseek/deepseek-v3.2-exp", alias="OPENROUTER_SECONDARY_MODEL")
    openrouter_secondary2_model: str = Field(default="z-ai/glm-5", alias="OPENROUTER_SECONDARY2_MODEL")
    openrouter_perplexity_model: str = Field(default="perplexity/sonar-pro-search", alias="OPENROUTER_PERPLEXITY_MODEL")

    perplexity_api_key: Optional[str] = Field(default=None, alias="PERPLEXITY_API_KEY")
    perplexity_base_url: str = Field(default="https://api.perplexity.ai", alias="PERPLEXITY_API_BASE_URL")
    perplexity_model: str = Field(default="sonar-pro", alias="PERPLEXITY_DEFAULT_MODEL")
    perplexity_timeout: int = Field(default=10, alias="PERPLEXITY_API_TIMEOUT")
    perplexity_max_retries: int = Field(default=3, alias="PERPLEXITY_API_MAX_RETRIES")
    perplexity_retry_delay: float = Field(default=2.0, alias="PERPLEXITY_API_RETRY_DELAY")

    # ── Supabase ────────────────────────────────────────────────────────
    supabase_url: str = Field(alias="SUPABASE_PROJECT_URL")
    supabase_anon_key: str = Field(alias="SUPABASE_ANON_PUBLIC")
    supabase_service_key: Optional[str] = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")

    # ── Redis ───────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")

    # ── Trading Parameters ──────────────────────────────────────────────
    mode: str = Field(default="paper", description="paper | demo | live")
    cycle_interval_seconds: int = Field(default=30, description="Main loop interval (Fast Paced)")
    quote_currency: str = Field(default="USDT")

    # Watcher
    watcher_min_volume_24h_usd: float = Field(default=2_000_000.0)
    watcher_top_n: int = Field(default=20)

    # Analyzer
    analyzer_timeframes: list[str] = Field(default=["5m", "15m", "1h", "4h"])
    # LOWERED FOR DEMO ("MAGIC") - typically 70.0
    analyzer_min_score: float = Field(default=30.0)
    analyzer_top_n: int = Field(default=5)

    # Risk & Position Management
    max_positions: int = Field(default=5)
    max_risk_per_trade_pct: float = Field(default=0.01, description="1% of equity per trade")
    max_portfolio_exposure_pct: float = Field(default=0.30, description="30% total exposure")
    max_single_exposure_pct: float = Field(default=0.08, description="8% single position")
    max_correlation: float = Field(default=0.7)
    max_drawdown_pct: float = Field(default=0.10, description="10% drawdown → safety mode")
    daily_loss_limit_pct: float = Field(default=0.03, description="3% daily loss limit")
    initial_equity_usd: float = Field(default=10_000.0)

    # Tier exits
    tier1_r_multiple: float = Field(default=2.0)
    tier1_exit_pct: float = Field(default=0.25)
    tier2_r_multiple: float = Field(default=5.0)
    tier2_exit_pct: float = Field(default=0.25)
    runner_trailing_stop_pct: float = Field(default=0.03)

    # Bayesian thresholds
    # LOWERED FOR DEMO ("MAGIC") - typically 0.65
    bayesian_threshold_normal: float = Field(default=0.30)
    bayesian_threshold_volatile: float = Field(default=0.75)
    bayesian_threshold_safety: float = Field(default=0.85)

    # Pyramid
    pyramid_enabled: bool = Field(default=True)
    pyramid_max_adds: int = Field(default=2)
    pyramid_min_r_to_add: float = Field(default=1.5)

    # ── Alerts ──────────────────────────────────────────────────────────
    discord_webhook: Optional[str] = Field(default=None, alias="DISCORD_WEBHOOK")
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")

    # ── Server / Monitoring ─────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    prometheus_port: int = Field(default=9090)

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
