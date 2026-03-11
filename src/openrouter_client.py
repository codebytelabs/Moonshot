import httpx
from loguru import logger

class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str = 'https://openrouter.ai/api/v1', model: str = 'gpt-4o-mini'):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model

    async def complete(self, prompt: str, temperature: float = 0.2, max_tokens: int = 800) -> str:
        payload = {
            'model': self.model,
            'messages': [{ 'role': 'user', 'content': prompt }],
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                return data['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
            return ''
