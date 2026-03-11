import httpx
import json
from loguru import logger

class PerplexityClient:
    def __init__(self, api_key: str, base_url: str = 'https://api.perplexity.ai', model: str = 'sonar'):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model

    async def analyze(self, symbol: str, snapshot: dict) -> dict:
        prompt = (
            f"Analyze why {symbol} is moving right now. "
            f"Snapshot: {json.dumps(snapshot)}. "
            "Return STRICT JSON with keys: catalysts (list), sentiment (bullish/bearish/neutral), "
            "sustainability_hours (number), confidence (0-1), risks (list)."
        )
        payload = {
            'model': self.model,
            'messages': [{ 'role': 'user', 'content': prompt }],
            'temperature': 0.2,
            'max_tokens': 600,
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
                content = data['choices'][0]['message']['content']
                # Try parse JSON; if fails, wrap raw content
                try:
                    return json.loads(content)
                except Exception:
                    return {'raw': content, 'confidence': 0.3, 'catalysts': [], 'risks': ['non_json_response']}
        except Exception as e:
            logger.error(f"Perplexity error: {e}")
            return {'error': str(e), 'confidence': 0.0, 'catalysts': [], 'risks': ['api_error']}
