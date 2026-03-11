from prometheus_client import Counter, Gauge

trades_total = Counter('trades_total', 'Total trades executed', ['exchange', 'symbol', 'side', 'mode'])
active_positions = Gauge('active_positions', 'Number of open positions')
portfolio_value = Gauge('portfolio_value', 'Portfolio value estimate')
