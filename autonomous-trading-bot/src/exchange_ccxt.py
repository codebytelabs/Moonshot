"""
Async CCXT exchange connector.
Gate.io as primary exchange; Binance/KuCoin as fallbacks.
Handles rate limiting, retries, market loading, and all trading operations.
"""
import asyncio
import time
from typing import Optional
from loguru import logger

import ccxt.async_support as ccxt_async
from .metrics import api_latency, errors_total


EXCHANGE_MAP = {
    "gateio": ccxt_async.gateio,
    "binance": ccxt_async.binance,
    "kucoin": ccxt_async.kucoin,
}


class ExchangeConnector:
    """Async exchange wrapper with rate limiting and retry logic."""

    def __init__(
        self,
        name: str = "gateio",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        extra: Optional[dict] = None,
        sandbox: bool = False,
        demo_url: Optional[str] = None,
    ):
        if name not in EXCHANGE_MAP:
            raise ValueError(f"Unsupported exchange: {name}. Supported: {list(EXCHANGE_MAP.keys())}")

        self.name = name
        self.demo_mode = demo_url is not None
        opts = {
            "enableRateLimit": True,
            "timeout": 30000,
        }
        if api_key and api_secret:
            opts["apiKey"] = api_key
            opts["secret"] = api_secret
        if extra:
            opts.update(extra)

        # When using demo mode, disable sapi/margin fetches that don't exist
        if demo_url:
            opts["options"] = opts.get("options", {})
            opts["options"]["fetchCurrencies"] = False
            opts["options"]["fetchMargins"] = False
            opts["options"]["fetchFundingRates"] = False
            opts["options"]["warnOnFetchOpenOrdersWithoutSymbol"] = False
            opts["options"]["defaultType"] = "spot"
            # Only load spot markets — skip futures, options, etc.
            opts["options"]["fetchMarkets"] = ["spot"]

        self.exchange: ccxt_async.Exchange = EXCHANGE_MAP[name](opts)

        if demo_url:
            # Override ALL API URLs to route through the demo server
            base = demo_url.rstrip("/")
            
            if name == "binance":
                self.exchange.urls["api"] = {
                    # Spot endpoints
                    "public": f"{base}/api/v3",
                    "private": f"{base}/api/v3",
                    "v3": f"{base}/api/v3",
                    "v1": f"{base}/api/v1",
                    # sapi endpoints (wallet, etc.)
                    "sapi": f"{base}/sapi/v1",
                    "sapiV2": f"{base}/sapi/v2",
                    "sapiV3": f"{base}/sapi/v3",
                    "sapiV4": f"{base}/sapi/v4",
                    # Futures (USDⓈ-M) — map to demo even though we won't call them
                    "fapiPublic": f"{base}/fapi/v1",
                    "fapiPublicV2": f"{base}/fapi/v2",
                    "fapiPublicV3": f"{base}/fapi/v3",
                    "fapiPrivate": f"{base}/fapi/v1",
                    "fapiPrivateV2": f"{base}/fapi/v2",
                    "fapiPrivateV3": f"{base}/fapi/v3",
                    "fapiData": f"{base}/futures/data",
                    # Coin-M futures
                    "dapiPublic": f"{base}/dapi/v1",
                    "dapiPrivate": f"{base}/dapi/v1",
                    "dapiPrivateV2": f"{base}/dapi/v2",
                    "dapiData": f"{base}/futures/data",
                    # European options
                    "eapiPublic": f"{base}/eapi/v1",
                    "eapiPrivate": f"{base}/eapi/v1",
                    # Portfolio margin
                    "papi": f"{base}/papi/v1",
                    "papiV2": f"{base}/papi/v2",
                }
            elif name == "gateio":
                # Gate.io has nested dicts for public/private endpoints
                if "api" in self.exchange.urls:
                    for section in ["public", "private"]:
                        if section in self.exchange.urls["api"]:
                            for key in self.exchange.urls["api"][section]:
                                self.exchange.urls["api"][section][key] = base
            
            # 🚨 Gate.io Testnet Check:
            # Testnet supports SPOT but fails on futures/swaps (Internal Error 500).
            # CCXT's default fetch_markets tries to load everything.
            # We must monkeypatch to ONLY load spot markets.
            if name == "gateio":
                logger.info("🔧 Monkeypatching Gate.io to load SPOT markets only (bypassing broken futures)")
                
                async def fetch_markets_spot_only(params={}):
                    return await self.exchange.fetch_spot_markets(params)
                
                self.exchange.fetch_markets = fetch_markets_spot_only

            logger.info(f"Exchange {name} set to DEMO MODE → {base}")
        elif sandbox:
            self.exchange.set_sandbox_mode(True)
            logger.info(f"Exchange {name} set to SANDBOX mode")

        self.markets_loaded = False
        self._last_request_time = 0.0

    async def initialize(self):
        """Load markets and log available pairs."""
        try:
            t0 = time.monotonic()
            await self.exchange.load_markets()
            elapsed = time.monotonic() - t0
            self.markets_loaded = True
            n_markets = len(self.exchange.markets)
            logger.info(f"[{self.name}] Loaded {n_markets} markets in {elapsed:.1f}s")
            api_latency.labels(exchange=self.name, endpoint="load_markets").observe(elapsed)
        except Exception as e:
            logger.error(f"[{self.name}] Failed to load markets: {e}")
            errors_total.labels(component="exchange", error_type="load_markets").inc()
            raise

    async def close(self):
        """Close exchange connection."""
        try:
            await self.exchange.close()
            logger.info(f"[{self.name}] Connection closed")
        except Exception as e:
            logger.error(f"[{self.name}] Error closing: {e}")

    # ── Market Data ─────────────────────────────────────────────────────

    async def fetch_tickers(self, symbols: Optional[list[str]] = None) -> dict:
        """Fetch all tickers or specific symbols. Returns {symbol: ticker_dict}."""
        return await self._retry(
            self.exchange.fetch_tickers, symbols, endpoint="fetch_tickers"
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
        limit: int = 200,
        since: Optional[int] = None,
    ) -> list:
        """Fetch OHLCV candles. Returns [[timestamp, O, H, L, C, V], ...]."""
        return await self._retry(
            self.exchange.fetch_ohlcv,
            symbol, timeframe, since, limit,
            endpoint="fetch_ohlcv",
        )

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Fetch order book. Returns {bids: [...], asks: [...], ...}."""
        return await self._retry(
            self.exchange.fetch_order_book, symbol, limit,
            endpoint="fetch_order_book",
        )

    async def fetch_ticker(self, symbol: str) -> dict:
        """Fetch a single ticker."""
        return await self._retry(
            self.exchange.fetch_ticker, symbol,
            endpoint="fetch_ticker",
        )

    # ── Account & Balance ───────────────────────────────────────────────

    async def fetch_balance(self) -> dict:
        """Fetch account balance."""
        return await self._retry(
            self.exchange.fetch_balance, endpoint="fetch_balance"
        )

    async def fetch_my_trades(self, symbol: str, limit: int = 50) -> list:
        """Fetch recent trades for a symbol."""
        return await self._retry(
            self.exchange.fetch_my_trades, symbol, None, limit,
            endpoint="fetch_my_trades",
        )

    # ── Order Execution ─────────────────────────────────────────────────

    async def create_market_buy(self, symbol: str, amount: float) -> dict:
        """Place a market buy order. Amount in base currency."""
        logger.info(f"[{self.name}] MARKET BUY {symbol} amount={amount}")
        return await self._retry(
            self.exchange.create_order,
            symbol, "market", "buy", amount,
            endpoint="create_order",
        )

    async def create_market_sell(self, symbol: str, amount: float) -> dict:
        """Place a market sell order."""
        logger.info(f"[{self.name}] MARKET SELL {symbol} amount={amount}")
        return await self._retry(
            self.exchange.create_order,
            symbol, "market", "sell", amount,
            endpoint="create_order",
        )

    async def create_limit_buy(self, symbol: str, amount: float, price: float) -> dict:
        """Place a limit buy order."""
        logger.info(f"[{self.name}] LIMIT BUY {symbol} amount={amount} price={price}")
        return await self._retry(
            self.exchange.create_order,
            symbol, "limit", "buy", amount, price,
            endpoint="create_order",
        )

    async def create_limit_sell(self, symbol: str, amount: float, price: float) -> dict:
        """Place a limit sell order."""
        logger.info(f"[{self.name}] LIMIT SELL {symbol} amount={amount} price={price}")
        return await self._retry(
            self.exchange.create_order,
            symbol, "limit", "sell", amount, price,
            endpoint="create_order",
        )

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel an open order."""
        logger.info(f"[{self.name}] CANCEL order={order_id} symbol={symbol}")
        return await self._retry(
            self.exchange.cancel_order, order_id, symbol,
            endpoint="cancel_order",
        )

    async def fetch_order(self, order_id: str, symbol: str) -> dict:
        """Fetch order status."""
        return await self._retry(
            self.exchange.fetch_order, order_id, symbol,
            endpoint="fetch_order",
        )

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> list:
        """Fetch all open orders."""
        return await self._retry(
            self.exchange.fetch_open_orders, symbol,
            endpoint="fetch_open_orders",
        )

    async def fetch_my_trades(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None) -> list:
        """Fetch user trade history."""
        return await self._retry(
            self.exchange.fetch_my_trades, symbol, since, limit,
            endpoint="fetch_my_trades",
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    def get_usdt_pairs(self, min_volume_usd: float = 0) -> list[str]:
        """Get all active USDT trading pairs, optionally filtered by 24h volume."""
        if not self.markets_loaded:
            return []
        pairs = []
        for symbol, market in self.exchange.markets.items():
            if (
                market.get("quote") == "USDT"
                and market.get("active", True)
                and market.get("spot", True)
            ):
                pairs.append(symbol)
        return pairs

    def get_market_info(self, symbol: str) -> Optional[dict]:
        """Get market info for a symbol (precision, limits, etc)."""
        return self.exchange.markets.get(symbol)

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        """Round amount to exchange precision."""
        return float(self.exchange.amount_to_precision(symbol, amount))

    def price_to_precision(self, symbol: str, price: float) -> float:
        """Round price to exchange precision."""
        return float(self.exchange.price_to_precision(symbol, price))

    # ── Retry Engine ────────────────────────────────────────────────────

    async def _retry(self, func, *args, endpoint: str = "unknown", max_retries: int = 3):
        """Execute with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                t0 = time.monotonic()
                result = await func(*args)
                elapsed = time.monotonic() - t0
                api_latency.labels(exchange=self.name, endpoint=endpoint).observe(elapsed)
                return result
            except ccxt_async.RateLimitExceeded as e:
                wait = 2 ** (attempt + 1)
                logger.warning(f"[{self.name}] Rate limited on {endpoint}, waiting {wait}s (attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(wait)
            except ccxt_async.NetworkError as e:
                wait = 2 ** attempt
                logger.warning(f"[{self.name}] Network error on {endpoint}: {e}, retrying in {wait}s")
                await asyncio.sleep(wait)
            except ccxt_async.ExchangeNotAvailable as e:
                wait = 5 * (attempt + 1)
                logger.error(f"[{self.name}] Exchange unavailable: {e}, retrying in {wait}s")
                await asyncio.sleep(wait)
            except ccxt_async.ExchangeError as e:
                logger.error(f"[{self.name}] Exchange error on {endpoint}: {e}")
                errors_total.labels(component="exchange", error_type="exchange_error").inc()
                raise
            except Exception as e:
                logger.error(f"[{self.name}] Unexpected error on {endpoint}: {e}")
                errors_total.labels(component="exchange", error_type="unexpected").inc()
                raise

        logger.error(f"[{self.name}] Max retries ({max_retries}) exhausted for {endpoint}")
        errors_total.labels(component="exchange", error_type="max_retries").inc()
        raise Exception(f"Max retries exhausted for {self.name}.{endpoint}")


class MultiExchangeManager:
    """Manage multiple exchange connections with primary/fallback."""

    def __init__(self):
        self.exchanges: dict[str, ExchangeConnector] = {}
        self.primary: Optional[str] = None

    async def add_exchange(
        self,
        name: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        extra: Optional[dict] = None,
        sandbox: bool = False,
        is_primary: bool = False,
    ):
        """Add and initialize an exchange."""
        connector = ExchangeConnector(name, api_key, api_secret, extra, sandbox)
        await connector.initialize()
        self.exchanges[name] = connector
        if is_primary or self.primary is None:
            self.primary = name
        logger.info(f"Added exchange: {name} (primary={is_primary})")

    def get_primary(self) -> ExchangeConnector:
        """Get the primary exchange connector."""
        if self.primary is None or self.primary not in self.exchanges:
            raise RuntimeError("No primary exchange configured")
        return self.exchanges[self.primary]

    def get(self, name: str) -> Optional[ExchangeConnector]:
        """Get a specific exchange by name."""
        return self.exchanges.get(name)

    async def close_all(self):
        """Close all exchange connections."""
        for name, connector in self.exchanges.items():
            await connector.close()
        self.exchanges.clear()
        self.primary = None
