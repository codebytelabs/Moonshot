import pandas as pd
import numpy as np
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator

class AnalyzerAgent:
    def __init__(self, min_score: float = 70.0):
        self.min_score = min_score

    def analyze(self, exchange, candidates: list[dict], timeframe='5m', limit=200, top_n=5) -> list[dict]:
        out = []
        for c in candidates:
            sym = c['symbol']
            raw = exchange.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(raw, columns=['ts','open','high','low','close','volume'])
            close = df['close']
            ema9 = EMAIndicator(close, window=9).ema_indicator().iloc[-1]
            ema21 = EMAIndicator(close, window=21).ema_indicator().iloc[-1]
            trend_up = ema9 > ema21

            atr = AverageTrueRange(df['high'], df['low'], close, window=14).average_true_range().iloc[-1]
            setup_type = 'trend_continuation' if trend_up else 'mean_reversion'

            # composite score (placeholder)
            composite = c['score'] + (10 if trend_up else 0)

            if composite >= self.min_score:
                out.append({
                    **c,
                    'trend_up': bool(trend_up),
                    'atr': float(atr),
                    'setup_type': setup_type,
                    'ta_score': float(composite),
                })

        out.sort(key=lambda x: x['ta_score'], reverse=True)
        return out[:top_n]
