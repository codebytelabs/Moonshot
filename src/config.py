from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    cycle_seconds: int = int(os.getenv('CYCLE_SECONDS', '300'))
    max_concurrent_positions: int = int(os.getenv('MAX_CONCURRENT_POSITIONS', '5'))
    max_risk_per_trade_pct: float = float(os.getenv('MAX_RISK_PER_TRADE_PCT', '0.01'))
    max_drawdown_pct: float = float(os.getenv('MAX_DRAWDOWN_PCT', '0.10'))

    perplexity_api_key: str | None = os.getenv('PERPLEXITY_API_KEY')
    perplexity_base_url: str = os.getenv('PERPLEXITY_BASE_URL', 'https://api.perplexity.ai')
    perplexity_model: str = os.getenv('PERPLEXITY_MODEL', 'sonar')

    openrouter_api_key: str | None = os.getenv('OPENROUTER_API_KEY')
    openrouter_base_url: str = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    openrouter_model: str = os.getenv('OPENROUTER_MODEL', 'gpt-4o-mini')

    supabase_url: str | None = os.getenv('SUPABASE_URL')
    supabase_key: str | None = os.getenv('SUPABASE_KEY')
