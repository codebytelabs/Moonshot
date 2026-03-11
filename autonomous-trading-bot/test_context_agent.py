import asyncio
import os
from dotenv import load_dotenv
import sys
from src.context_agent import ContextAgent
from src.openrouter_client import OpenRouterClient

# Load env with override
load_dotenv("../.env", override=True)

async def test_enrich():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ No API Key found")
        return

    print(f"🔑 Using API Key: {api_key[:6]}...")
    
    # Init client
    client = OpenRouterClient(api_key=api_key)
    
    # Init agent with Perplexity model
    model = os.getenv("OPENROUTER_PERPLEXITY_MODEL", "perplexity/sonar-pro-search")
    print(f"🤖 Using Model: {model}")
    
    agent = ContextAgent(openrouter_client=client, model_id=model)
    
    # Create dummy setups (7 items to test chunking of 5)
    setups = [
        {"symbol": "BTC", "setup_type": "breakout", "ta_score": 85, "features": {"current_price": 95000}},
        {"symbol": "ETH", "setup_type": "pullback", "ta_score": 78, "features": {"current_price": 2700}},
        {"symbol": "SOL", "setup_type": "momentum", "ta_score": 92, "features": {"current_price": 145}},
        {"symbol": "XRP", "setup_type": "neutral", "ta_score": 60, "features": {"current_price": 2.5}},
        {"symbol": "DOGE", "setup_type": "breakout", "ta_score": 88, "features": {"current_price": 0.5}},
        {"symbol": "ADA", "setup_type": "mean_reversion", "ta_score": 70, "features": {"current_price": 1.1}},
        {"symbol": "AVAX", "setup_type": "pullback", "ta_score": 75, "features": {"current_price": 35}},
    ]
    
    print(f"🧪 Testing batch enrichment of {len(setups)} items...")
    
    try:
        enriched = await agent.enrich(setups)
        
        print(f"\n✅ Enriched {len(enriched)} items!")
        for item in enriched:
            ctx = item.get("context", {})
            print(f"   • {item['symbol']}: {ctx.get('sentiment')} (conf: {ctx.get('confidence')})")
            print(f"     Summary: {ctx.get('summary')}")
            print(f"     Drivers: {ctx.get('catalysts')}\n")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_enrich())
