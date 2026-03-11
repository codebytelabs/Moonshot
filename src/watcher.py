import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

class WatcherAgent:
    def __init__(self, min_quote_volume: float = 5_000_000):
        self.min_quote_volume = min_quote_volume

    def score_symbol(self, ohlcv_df: pd.DataFrame, quote_volume_24h: float) -> dict | None:
        if quote_volume_24h is None or quote_volume_24h < self.min_quote_volume:
            return None

        close = ohlcv_df['close']
        rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
        ema3 = EMAIndicator(close, window=3).ema_indicator().iloc[-1]
        ema20 = EMAIndicator(close, window=20).ema_indicator().iloc[-1]

        # Simple momentum/quality scoring (placeholder)
        score = 0
        if 40 <= rsi <= 70:
            score += 30
        if ema3 > ema20:
            score += 40
        # volume proxy: last candle vs median
        vol = ohlcv_df['volume']
        if vol.iloc[-1] > vol.iloc[-51:-1].median() * 1.5:
            score += 30

        return {
            'rsi': float(rsi),
            'ema3': float(ema3),
            'ema20': float(ema20),
            'score': float(score),
        }

    def scan(self, exchange, symbols: list[str], timeframe='5m', limit=200, top_n=15) -> list[dict]:
        out = []
        for sym in symbols:
            t = exchange.fetch_ticker(sym)
            qv = t.get('quoteVolume')
            raw = exchange.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(raw, columns=['ts','open','high','low','close','volume'])
            df['ts'] = pd.to_datetime(df['ts'], unit='ms')
            scored = self.score_symbol(df, qv)
            if scored:
                scored.update({'symbol': sym, 'quote_volume_24h': float(qv or 0.0), 'last': float(t.get('last') or df['close'].iloc[-1])})
                out.append(scored)
        out.sort(key=lambda x: x['score'], reverse=True)
        return out[:top_n]
