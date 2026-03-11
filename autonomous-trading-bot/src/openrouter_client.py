"""
OpenRouter LLM client.
Provides chat completions via OpenRouter API with retry, model fallback, and streaming.
"""
import json
import asyncio
from typing import Optional
from loguru import logger
import httpx

from .metrics import api_latency, errors_total


class OpenRouterClient:
    """Async OpenRouter API client for LLM chat completions."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        primary_model: str = "google/gemini-3-flash-preview",
        secondary_model: str = "deepseek/deepseek-v3.2-exp",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.primary_model = primary_model
        self.secondary_model = secondary_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._history: list[dict] = []

    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        use_history: bool = False,
    ) -> str:
        """
        Send a chat completion request.
        Returns the assistant's response text.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if use_history:
            messages.extend(self._history[-10:])  # Last 5 turns

        messages.append({"role": "user", "content": prompt})

        # Try primary model, then fallback
        models_to_try = [model or self.primary_model, self.secondary_model]

        for m in models_to_try:
            response = await self._request(messages, m, temperature, max_tokens)
            if response:
                if use_history:
                    self._history.append({"role": "user", "content": prompt})
                    self._history.append({"role": "assistant", "content": response})
                return response

        return "LLM response unavailable"

    async def _request(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Optional[str]:
        """Make the API request with retry."""
        for attempt in range(self.max_retries):
            try:
                import time
                t0 = time.monotonic()

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://moonshot-trading-bot.local",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    )

                elapsed = time.monotonic() - t0
                api_latency.labels(exchange="openrouter", endpoint="chat").observe(elapsed)

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
                elif resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"OpenRouter rate limited, waiting {wait}s")
                    await asyncio.sleep(wait)
                else:
                    logger.warning(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)

            except httpx.TimeoutException:
                logger.warning(f"OpenRouter timeout (attempt {attempt+1}/{self.max_retries})")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"OpenRouter error: {e}")
                errors_total.labels(component="openrouter", error_type="request").inc()
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        return None

    def clear_history(self):
        """Clear conversation history."""
        self._history.clear()
