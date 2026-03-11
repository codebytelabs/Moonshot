"""
Redis caching layer.
Provides ticker/OHLCV caching, pub/sub helpers, and graceful fallback if Redis is unreachable.
"""
import json
from typing import Any, Optional
from loguru import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed — caching disabled")


class RedisClient:
    """Async Redis wrapper with graceful degradation."""

    def __init__(self, url: str = "redis://localhost:6379/0", password: Optional[str] = None):
        self.url = url
        self.password = password
        self._pool: Optional[Any] = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection pool. Returns True if connected."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis unavailable (package not installed)")
            return False
        try:
            self._pool = aioredis.from_url(
                self.url,
                password=self.password,
                decode_responses=True,
                max_connections=20,
            )
            await self._pool.ping()
            self._connected = True
            logger.info("Redis connected", url=self.url)
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} — caching disabled")
            self._connected = False
            return False

    async def close(self):
        """Close connection pool."""
        if self._pool and self._connected:
            await self._pool.close()
            self._connected = False
            logger.info("Redis disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Ticker cache ────────────────────────────────────────────────────

    async def cache_ticker(self, symbol: str, data: dict, ttl: int = 30) -> bool:
        """Cache a single ticker snapshot. TTL in seconds."""
        if not self._connected:
            return False
        try:
            key = f"ticker:{symbol}"
            await self._pool.setex(key, ttl, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Redis cache_ticker failed: {e}")
            return False

    async def get_ticker(self, symbol: str) -> Optional[dict]:
        """Retrieve cached ticker or None."""
        if not self._connected:
            return None
        try:
            raw = await self._pool.get(f"ticker:{symbol}")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error(f"Redis get_ticker failed: {e}")
            return None

    # ── OHLCV cache ─────────────────────────────────────────────────────

    async def cache_ohlcv(self, symbol: str, timeframe: str, data: list, ttl: int = 300) -> bool:
        """Cache OHLCV candle data. TTL in seconds."""
        if not self._connected:
            return False
        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            await self._pool.setex(key, ttl, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Redis cache_ohlcv failed: {e}")
            return False

    async def get_ohlcv(self, symbol: str, timeframe: str) -> Optional[list]:
        """Retrieve cached OHLCV or None."""
        if not self._connected:
            return None
        try:
            raw = await self._pool.get(f"ohlcv:{symbol}:{timeframe}")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error(f"Redis get_ohlcv failed: {e}")
            return None

    # ── Generic cache ───────────────────────────────────────────────────

    async def set(self, key: str, value: Any, ttl: int = 60) -> bool:
        """Generic set with TTL."""
        if not self._connected:
            return False
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            await self._pool.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis set failed: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Generic get."""
        if not self._connected:
            return None
        try:
            raw = await self._pool.get(key)
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            return None

    # ── Pub/Sub ─────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: Any) -> bool:
        """Publish a message to a Redis channel."""
        if not self._connected:
            return False
        try:
            serialized = json.dumps(message) if not isinstance(message, str) else message
            await self._pool.publish(channel, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis publish failed: {e}")
            return False
