import argparse
import os
import asyncio
from dotenv import load_dotenv
from loguru import logger

from .config import Settings
from .utils.logger import setup_logging
from .connectors.exchange_ccxt import ExchangeConnector
from .connectors.perplexity_client import PerplexityClient
from .agents.watcher import WatcherAgent
from .agents.analyzer import AnalyzerAgent
from .agents.context_agent import ContextAgent
from .agents.bigbrother import BigBrotherAgent
from .engines.bayesian_engine import BayesianEngine
from .engines.risk_manager import RiskManager
from .position_manager import PositionManager

load_dotenv()

async def run_once(exchange_name: str, mode: str, symbols: list[str]):
    settings = Settings()
    setup_logging()

    # Exchange keys (optional for data)
    api_key = os.getenv(f"{exchange_name.upper()}_API_KEY")
    api_secret = os.getenv(f"{exchange_name.upper()}_API_SECRET")

    extra = {}
    if exchange_name == 'gateio':
        uid = os.getenv('GATEIO_UID')
        if uid:
            extra['uid'] = uid

    ex = ExchangeConnector(exchange_name, api_key=api_key, api_secret=api_secret, extra=extra)

    # Optional Perplexity
    pplx = None
    if settings.perplexity_api_key:
        pplx = PerplexityClient(settings.perplexity_api_key, settings.perplexity_base_url, settings.perplexity_model)

    watcher = WatcherAgent()
    analyzer = AnalyzerAgent()
    context_agent = ContextAgent(pplx)
    bayes = BayesianEngine(base_prior=0.60)
    risk = RiskManager(settings.max_risk_per_trade_pct, settings.max_concurrent_positions)
    boss = BigBrotherAgent(settings.max_drawdown_pct)

    pm = PositionManager(ex, mode=mode)

    # Metrics snapshot (placeholder)
    metrics = {'current_drawdown_pct': 0.0}
    bot_mode = boss.decide_mode(metrics)

    logger.info(f"Cycle start. exchange={exchange_name} mode={mode} bot_mode={bot_mode} symbols={len(symbols)}")

    candidates = watcher.scan(ex, symbols)
    logger.info(f"Watcher candidates: {len(candidates)}")

    shortlist = analyzer.analyze(ex, candidates)
    logger.info(f"Analyzer shortlist: {len(shortlist)}")

    enriched = []
    for c in shortlist:
        enriched.append(await context_agent.enrich(c))

    for c in enriched:
        ctx_conf = float(c.get('context', {}).get('confidence', 0.0) or 0.0)
        post = bayes.posterior(ta_score=c.get('ta_score', c.get('score', 0.0)), context_confidence=ctx_conf)
        enter = bayes.should_enter(post, bot_mode)
        logger.info(f"{c['symbol']} posterior={post:.2%} enter={enter} ta={c.get('ta_score')} ctx={ctx_conf}")
        if enter:
            # estimate equity in USDT (placeholder; you can compute from balances)
            equity = 10_000.0
            notional = risk.position_size_usd(equity, post)
            pm.execute_entry(c['symbol'], notional_usd=notional, limit_price=c.get('last'))

    logger.info("Cycle end")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['paper','live'], default='paper')
    p.add_argument('--exchange', choices=['binance','gateio','kucoin'], default='binance')
    p.add_argument('--symbols', default='BTC/USDT,ETH/USDT')
    return p.parse_args()


def main():
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(',') if s.strip()]
    asyncio.run(run_once(args.exchange, args.mode, symbols))

if __name__ == '__main__':
    main()
