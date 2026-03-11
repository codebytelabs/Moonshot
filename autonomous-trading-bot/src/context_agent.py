"""
Context Agent — AI Market Intelligence.
Uses OpenRouter (DeepSeek/Perplexity) to enrich technical setups with
sentiment, news, and fundamental context via batched analysis.
"""
import time
import json
import asyncio
from typing import Optional
from loguru import logger

from .openrouter_client import OpenRouterClient
from .redis_client import RedisClient
from .supabase_client import SupabaseStore
from .metrics import signals_generated


SYSTEM_PROMPT = """You are a crypto market intelligence analyst.
Analyze the provided list of tokens based on current market data and news.
Return a STRICT JSON array of objects. Do not include markdown formatting.
Schema per object:
{
  "symbol": "BTC",
  "sentiment": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "catalysts": ["list of key drivers"],
  "risks": ["list of risks"],
  "driver_type": "narrative" | "technical" | "fundamental" | "whale" | "unknown",
  "summary": "Brief 1-sentence summary"
}"""


class ContextAgent:
    """
    Enriches technical setups with market context using batched LLM calls.
    Optimized for cost and rate limits by processing multiple symbols in one prompt.
    """

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        redis: Optional[RedisClient] = None,
        store: Optional[SupabaseStore] = None,
        model_id: str = "perplexity/sonar-pro-search",
        cache_ttl: int = 900,  # 15 minutes
    ):
        self.llm = openrouter_client
        self.redis = redis
        self.store = store
        self.model_id = model_id
        self.cache_ttl = cache_ttl

    async def enrich(self, setups: list[dict]) -> list[dict]:
        """
        Enrich a list of Analyzer setups with market context.
        Returns same list with 'context' key added to each.
        """
        if not setups:
            return []

        logger.info(f"Context Agent: Processing {len(setups)} setups")
        
        # 1. Check cache first
        symbols_to_fetch = []
        cached_results = {}

        for setup in setups:
            symbol = setup["symbol"]
            cached = await self._get_cached_context(symbol)
            if cached:
                cached_results[symbol] = cached
                setup["context"] = cached
            else:
                symbols_to_fetch.append(setup)

        # 2. Batch fetch missing contexts
        if symbols_to_fetch:
            # Process in chunks of 5 to avoid huge prompts/timeouts
            chunk_size = 5
            for i in range(0, len(symbols_to_fetch), chunk_size):
                chunk = symbols_to_fetch[i : i + chunk_size]
                try:
                    results = await self._analyze_batch(chunk)
                    for res in results:
                        sym = res.get("symbol")
                        if sym:
                            cached_results[sym] = res
                            # Cache explicitly
                            if self.redis:
                                await self.redis.set(
                                    f"context:{sym}",
                                    res,
                                    ttl=self.cache_ttl
                                )
                except Exception as e:
                    logger.error(f"Context Agent: Batch analysis failed: {e}")

        # 3. Merge results back into setups
        enriched = []
        for setup in setups:
            symbol = setup["symbol"]
            # If we found a result (cached or fetched), use it
            if symbol in cached_results:
                setup["context"] = cached_results[symbol]
                
                # Metrics & Persistence
                signals_generated.labels(agent="context").inc()
                if self.store:
                    ctx = setup["context"]
                    self.store.insert_context_analysis(
                        symbol=symbol,
                        sentiment=ctx.get("sentiment", "neutral"),
                        confidence=ctx.get("confidence", 0.0),
                        catalysts=ctx.get("catalysts", []),
                        risks=ctx.get("risks", []),
                        driver_type=ctx.get("driver_type", "unknown"),
                        narrative_strength=0.0, # deprecated
                    )
            else:
                # Fallback if analysis failed
                setup["context"] = self._fallback_context(symbol)
            
            enriched.append(setup)

        return enriched

    async def _analyze_batch(self, chunk: list[dict]) -> list[dict]:
        """Call LLM with a batch of symbols."""
        symbols = [s["symbol"] for s in chunk]
        snapshots = []
        for s in chunk:
            # Create a minimal snapshot to save tokens
            snap = {
                "symbol": s["symbol"],
                "price": s.get("features", {}).get("current_price"),
                "setup": s.get("setup_type"),
                "ta_score": s.get("ta_score"),
            }
            snapshots.append(snap)
        
        prompt = (
            f"Analyze these crypto tokens: {', '.join(symbols)}. \n"
            f"Market Data: {json.dumps(snapshots)}. \n"
            "Provide independent analysis for each. Return strictly a JSON array."
        )

        logger.info(f"Context Agent: Batch analyzing {symbols} using {self.model_id}")
        
        response = await self.llm.chat(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            model=self.model_id,
            temperature=0.1
        )

        if not response or "unavailable" in response:
            return []

        try:
            # Robust JSON extraction
            clean = response.strip()
            # Find array start/end
            start = clean.find("[")
            end = clean.rfind("]")
            
            if start != -1 and end != -1:
                clean = clean[start : end + 1]
            
            # Remove markdown if stuck inside (rare)
            clean = clean.replace("```json", "").replace("```", "")
            
            data = json.loads(clean)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "coins" in data:
                return data["coins"]
            # Handle single object wrapped
            if isinstance(data, dict):
                return [data]
            return []
        except json.JSONDecodeError:
            logger.error(f"Context Agent: Failed to parse JSON: {response[:100]}...")
            return []

    async def _get_cached_context(self, symbol: str) -> Optional[dict]:
        if self.redis:
            return await self.redis.get(f"context:{symbol}")
        return None

    def _fallback_context(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "sentiment": "neutral",
            "confidence": 0.0,
            "catalysts": ["Analysis failed or skipped"],
            "risks": [],
            "driver_type": "unknown",
            "summary": "Automated context unavailable."
        }
