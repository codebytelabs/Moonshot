import os
import httpx
from loguru import logger

async def discord_alert(message: str):
    url = os.getenv('DISCORD_WEBHOOK')
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={"content": message})
    except Exception as e:
        logger.error(f"Discord alert failed: {e}")
