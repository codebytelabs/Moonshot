class ContextAgent:
    def __init__(self, perplexity_client=None):
        self.client = perplexity_client

    async def enrich(self, candidate: dict) -> dict:
        if not self.client:
            candidate['context'] = {'confidence': 0.0, 'catalysts': [], 'risks': ['context_disabled']}
            return candidate

        snapshot = {
            'symbol': candidate['symbol'],
            'last': candidate.get('last'),
            'quote_volume_24h': candidate.get('quote_volume_24h'),
            'rsi': candidate.get('rsi'),
            'score': candidate.get('score'),
            'setup_type': candidate.get('setup_type'),
        }
        ctx = await self.client.analyze(candidate['symbol'], snapshot)
        candidate['context'] = ctx
        return candidate
