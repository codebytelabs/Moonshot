import ccxt
from loguru import logger

EXCHANGE_MAP = {
    'binance': ccxt.binance,
    'gateio': ccxt.gateio,
    'kucoin': ccxt.kucoin,
}

class ExchangeConnector:
    def __init__(self, name: str, api_key: str | None = None, api_secret: str | None = None, extra: dict | None = None):
        if name not in EXCHANGE_MAP:
            raise ValueError(f"Unsupported exchange: {name}")
        opts = {
            'enableRateLimit': True,
        }
        if api_key and api_secret:
            opts['apiKey'] = api_key
            opts['secret'] = api_secret
        if extra:
            opts.update(extra)
        self.exchange = EXCHANGE_MAP[name](opts)
        self.name = name

    def fetch_ohlcv(self, symbol: str, timeframe='5m', limit=200):
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def fetch_ticker(self, symbol: str):
        return self.exchange.fetch_ticker(symbol)

    def create_limit_buy(self, symbol: str, amount: float, price: float):
        return self.exchange.create_limit_buy_order(symbol, amount, price)

    def create_limit_sell(self, symbol: str, amount: float, price: float):
        return self.exchange.create_limit_sell_order(symbol, amount, price)

    def fetch_balance(self):
        return self.exchange.fetch_balance()
