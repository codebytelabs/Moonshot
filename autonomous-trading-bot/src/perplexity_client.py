"""
Perplexity AI client for real-time market context analysis.
Includes retry logic, response validation, system prompt for structured JSON output.
"""
import json
import asyncio
from typing import Optional
from loguru import logger
import httpx

from .metrics import api_latency, errors_total


SYSTEM_PROMPT = """You are a crypto market intelligence analyst. When given a token symbol and market snapshot,
provide a structured JSON analysis. Always respond with valid JSON matching this schema:
{
  "sentiment": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "catalysts": ["list of current catalysts driving the move"],
  "risks": ["list of identified risks"],
  "driver_type": "narrative" | "technical" | "fundamental" | "whale" | "unknown",
  "narrative_strength": 0.0-1.0,
  "sustainability_hours": 1-168,
  "summary": "brief 1-2 sentence summary"
}
Do not include any text outside the JSON object."""


class PerplexityClient:
    """Async Perplexity API client with retry and structured output."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.perplexity.ai",
        model: str = "sonar-pro",
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def analyze(self, symbol: str, snapshot: dict) -> dict:
        """
        Analyze a token's current market situation.
        Returns structured dict with sentiment, catalysts, risks, etc.
        """
        user_prompt = (
            f"Analyze why {symbol} is moving right now. "
            f"Market snapshot: {json.dumps(snapshot)}. "
            f"Focus on: catalysts, sentiment, risk factors, whether the move is sustainable. "
            f"Respond with structured JSON only."
        )

        for attempt in range(self.max_retries):
            try:
                import time
                t0 = time.monotonic()

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.1,
                            "max_tokens": 800,
                        },
                    )

                elapsed = time.monotonic() - t0
                api_latency.labels(exchange="perplexity", endpoint="analyze").observe(elapsed)

                if response.status_code != 200:
                    logger.warning(
                        f"Perplexity API {response.status_code}: {response.text[:200]} "
                        f"(attempt {attempt+1}/{self.max_retries})"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                        continue
                    return self._fallback_response(symbol, "api_error")

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = self._parse_response(content)

                if parsed:
                    logger.debug(f"Perplexity analysis for {symbol}: sentiment={parsed.get('sentiment')}")
                    return parsed
                else:
                    logger.warning(f"Failed to parse Perplexity response for {symbol}")
                    return self._fallback_response(symbol, "parse_error")

            except httpx.TimeoutException:
                logger.warning(f"Perplexity timeout for {symbol} (attempt {attempt+1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
            except Exception as e:
                logger.error(f"Perplexity error for {symbol}: {e} (attempt {attempt+1}/{self.max_retries})")
                errors_total.labels(component="perplexity", error_type="request").inc()
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

        return self._fallback_response(symbol, "max_retries_exceeded")

    def _parse_response(self, content: str) -> Optional[dict]:
        """Parse the LLM response, extracting JSON even if wrapped in markdown."""
        parsed = None
        
        # Try direct JSON parse
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        if parsed is None and "```json" in content:
            try:
                json_str = content.split("```json")[1].split("```")[0].strip()
                parsed = json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        if parsed is None and "```" in content:
            try:
                json_str = content.split("```")[1].split("```")[0].strip()
                parsed = json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        # Try finding JSON object in the text
        if parsed is None:
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                parsed = json.loads(content[start:end])
            except (ValueError, json.JSONDecodeError):
                pass

        # Validate and clamp values if parsing succeeded
        if parsed is not None:
            parsed = self._validate_and_clamp(parsed)
        
        return parsed
    
    def _validate_and_clamp(self, data: dict) -> dict:
        """
        Validate and clamp LLM response values to ensure they meet requirements.
        Per Requirement 4.6: sentiment must be {bullish, bearish, neutral},
        confidence and narrative_strength must be in [0.0, 1.0].
        """
        # Validate sentiment
        if "sentiment" in data:
            if data["sentiment"] not in ["bullish", "bearish", "neutral"]:
                logger.warning(f"Invalid sentiment '{data['sentiment']}', defaulting to 'neutral'")
                data["sentiment"] = "neutral"
        
        # Clamp confidence to [0.0, 1.0]
        if "confidence" in data:
            try:
                conf = float(data["confidence"])
                if conf < 0.0:
                    logger.warning(f"Confidence {conf} < 0.0, clamping to 0.0")
                    data["confidence"] = 0.0
                elif conf > 1.0:
                    logger.warning(f"Confidence {conf} > 1.0, clamping to 1.0")
                    data["confidence"] = 1.0
                else:
                    data["confidence"] = conf
            except (ValueError, TypeError):
                logger.warning(f"Invalid confidence value '{data['confidence']}', defaulting to 0.0")
                data["confidence"] = 0.0
        
        # Clamp narrative_strength to [0.0, 1.0]
        if "narrative_strength" in data:
            try:
                ns = float(data["narrative_strength"])
                if ns < 0.0:
                    logger.warning(f"narrative_strength {ns} < 0.0, clamping to 0.0")
                    data["narrative_strength"] = 0.0
                elif ns > 1.0:
                    logger.warning(f"narrative_strength {ns} > 1.0, clamping to 1.0")
                    data["narrative_strength"] = 1.0
                else:
                    data["narrative_strength"] = ns
            except (ValueError, TypeError):
                logger.warning(f"Invalid narrative_strength value '{data['narrative_strength']}', defaulting to 0.0")
                data["narrative_strength"] = 0.0
        
        return data

    @staticmethod
    def _fallback_response(symbol: str, reason: str) -> dict:
        """Return a safe fallback when analysis fails."""
        return {
            "sentiment": "neutral",
            "confidence": 0.0,
            "catalysts": [],
            "risks": [f"context_unavailable_{reason}"],
            "driver_type": "unknown",
            "narrative_strength": 0.0,
            "sustainability_hours": 0,
            "summary": f"Analysis unavailable for {symbol}: {reason}",
        }
