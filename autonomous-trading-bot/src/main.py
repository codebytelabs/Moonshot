"""
Main Orchestrator — Trading bot entry point.
Initialization → Trading loop → Graceful shutdown.
"""
import asyncio
import signal
import time
import sys
from loguru import logger

from .config import get_settings
from .logger import setup_logging
from .redis_client import RedisClient
from .supabase_client import SupabaseStore
from .exchange_ccxt import ExchangeConnector
from .openrouter_client import OpenRouterClient
from .watcher import WatcherAgent
from .analyzer import AnalyzerAgent
from .context_agent import ContextAgent
from .bayesian_engine import BayesianDecisionEngine
from .risk_manager import RiskManager
from .position_manager import PositionManager
from .bigbrother import BigBrotherAgent
from .alerts import AlertManager
from .api import create_app, broadcast_ws
from .metrics import cycle_duration, errors_total, account_equity, portfolio_value


class TradingBot:
    """Main orchestrator — wires up all components and runs the trading loop."""

    def __init__(self):
        self.settings = get_settings()
        self.running = False

        # Components (initialized in start())
        self.redis: RedisClient | None = None
        self.store: SupabaseStore | None = None
        self.exchange: ExchangeConnector | None = None
        self.openrouter: OpenRouterClient | None = None
        self.watcher: WatcherAgent | None = None
        self.analyzer: AnalyzerAgent | None = None
        self.context: ContextAgent | None = None
        self.engine: BayesianDecisionEngine | None = None
        self.risk: RiskManager | None = None
        self.pm: PositionManager | None = None
        self.bigbrother: BigBrotherAgent | None = None
        self.alerts: AlertManager | None = None

    async def start(self):
        """Initialize all components and start the trading loop."""
        s = self.settings
        setup_logging(debug=s.mode != "live")

        logger.info("=" * 60)
        logger.info("🚀 MOONSHOT Trading Bot — Starting")
        logger.info(f"   Mode: {s.mode} | Exchange: {s.exchange_name}")
        logger.info(f"   Equity: ${s.initial_equity_usd:,.0f} | Max Positions: {s.max_positions}")
        logger.info("=" * 60)

        # Redis
        self.redis = RedisClient(s.redis_url, s.redis_password)
        await self.redis.connect()

        # Supabase
        self.store = SupabaseStore(s.supabase_url, s.supabase_anon_key)

        # Exchange — select credentials based on mode
        demo_url = None
        exchange_name = s.exchange_name

        if s.exchange_mode == "demo":
            # Demo mode: real orders on demo/testnet exchange
            s.mode = "demo"
            if s.exchange_name == "binance":
                api_key = s.binance_demo_api_key
                api_secret = s.binance_demo_api_secret
                demo_url = s.binance_demo_url
                logger.info("📡 DEMO MODE — Using Binance Demo API")
            elif s.exchange_name == "gateio":
                api_key = s.gateio_testnet_api_key
                api_secret = s.gateio_testnet_secret_key
                demo_url = s.gateio_testnet_url
                logger.info("📡 DEMO MODE — Using Gate.io Testnet API")
            else:
                raise ValueError(f"Demo mode not supported for {s.exchange_name}")
        else:
            api_key = s.gateio_api_key if s.exchange_name == "gateio" else s.binance_api_key
            api_secret = s.gateio_api_secret if s.exchange_name == "gateio" else s.binance_api_secret

        self.exchange = ExchangeConnector(
            name=exchange_name,
            api_key=api_key,
            api_secret=api_secret,
            sandbox=(s.mode == "paper"),
            demo_url=demo_url,
        )
        await self.exchange.initialize()

        # LLM clients
        self.openrouter = OpenRouterClient(
            api_key=s.openrouter_api_key,
            base_url=s.openrouter_base_url,
            primary_model=s.openrouter_primary_model,
            secondary_model=s.openrouter_secondary_model,
        )

        # Agents
        self.watcher = WatcherAgent(
            exchange=self.exchange,
            redis=self.redis,
            store=self.store,
            min_volume_24h_usd=s.watcher_min_volume_24h_usd,
            top_n=s.watcher_top_n,
        )
        self.analyzer = AnalyzerAgent(
            exchange=self.exchange,
            redis=self.redis,
            store=self.store,
            timeframes=s.analyzer_timeframes,
            min_score=s.analyzer_min_score,
            top_n=s.analyzer_top_n,
        )
        # Context Agent (uses OpenRouter Perplexity model)
        self.context = ContextAgent(
            openrouter_client=self.openrouter,
            redis=self.redis,
            store=self.store,
            model_id=s.openrouter_perplexity_model,  # Use configured OpenRouter Perplexity model
        )

        # Decision & Risk
        self.risk = RiskManager(s)
        self.engine = BayesianDecisionEngine(store=self.store, mode="normal")
        self.pm = PositionManager(
            exchange=self.exchange,
            settings=s,
            store=self.store,
            paper_mode=(s.mode == "paper"),  # False for demo & live
        )

        # Alerts
        self.alerts = AlertManager(
            discord_webhook=s.discord_webhook,
            telegram_token=s.telegram_bot_token,
            telegram_chat_id=s.telegram_chat_id,
        )

        # BigBrother
        self.bigbrother = BigBrotherAgent(
            risk_manager=self.risk,
            decision_engine=self.engine,
            store=self.store,
            openrouter_client=self.openrouter,
            alert_fn=self.alerts.send,
        )

        # Start trading loop
        self.running = True
        await self.alerts.send(
            f"🚀 Bot started in **{s.mode}** mode on **{s.exchange_name}**\n"
            f"Equity: ${s.initial_equity_usd:,.0f} | Max positions: {s.max_positions}",
            priority="medium",
        )
        await self._trading_loop()

    async def _trading_loop(self):
        """Main trading cycle."""
        cycle = 0
        while self.running:
            cycle += 1
            logger.info(f"{'─' * 40} Cycle {cycle} {'─' * 40}")
            t0 = time.monotonic()

            try:
                # 1. Watcher: scan market
                candidates = await self.watcher.scan()
                if not candidates:
                    logger.info("No candidates found this cycle")
                    await self._sleep()
                    continue

                # 2. Analyzer: deep TA
                setups = await self.analyzer.analyze(candidates)
                if not setups:
                    logger.info("No setups passed analysis")
                    await self._sleep()
                    continue

                # 3. Context: enrich with market intelligence
                enriched = await self.context.enrich(setups)

                # 4. Bayesian: decide
                self.risk.set_open_positions(self.pm.get_open_positions())
                decisions = self.engine.batch_decide(enriched)

                # 5. Position Manager: execute entries
                for decision in decisions:
                    symbol = decision["symbol"]
                    can_open, reason = self.risk.can_open_position(symbol, decision)
                    if not can_open:
                        logger.info(f"Risk blocked {symbol}: {reason}")
                        continue

                    entry_zone = decision.get("entry_zone", {})
                    size = self.risk.position_size_usd(
                        entry_price=entry_zone.get("entry", 0),
                        stop_loss=entry_zone.get("stop_loss", 0),
                        posterior=decision.get("posterior", 0.65),
                    )
                    if size < 10:
                        logger.info(f"Position size too small for {symbol}: ${size:.2f}")
                        continue

                    pos = await self.pm.open_position(
                        symbol=symbol,
                        size_usd=size,
                        entry_zone=entry_zone,
                        setup_type=decision.get("setup_type", "unknown"),
                        posterior=decision.get("posterior", 0),
                    )
                    if pos:
                        await self.alerts.send(
                            f"📈 Opened: {symbol} @ ${pos.entry_price:.6f}\n"
                            f"Size: ${pos.notional_usd:.2f} | Stop: ${pos.stop_loss:.6f}\n"
                            f"Setup: {pos.setup_type} | Posterior: {pos.posterior:.3f}",
                            priority="medium",
                        )

                # 6. Update existing positions
                tickers = await self.exchange.fetch_tickers()
                await self.pm.update_prices(tickers)

                # 7. BigBrother supervision
                supervision = await self.bigbrother.supervise()

                # 8. Broadcast state via WebSocket
                await broadcast_ws({
                    "cycle": cycle,
                    "mode": supervision.get("mode", "normal"),
                    "positions": self.pm.get_open_positions(),
                    "health": supervision.get("health", {}),
                    "candidates": len(candidates),
                    "setups": len(setups),
                    "entries": len(decisions),
                })

                # Update equity gauge
                health = supervision.get("health", {})
                account_equity.set(health.get("equity", 0))

            except Exception as e:
                logger.error(f"Cycle {cycle} error: {e}")
                errors_total.labels(component="main", error_type="cycle_error").inc()
                await self.alerts.send(f"❌ Cycle {cycle} error: {e}", priority="high")

            elapsed = time.monotonic() - t0
            cycle_duration.observe(elapsed)
            logger.info(f"Cycle {cycle} completed in {elapsed:.1f}s")

            await self._sleep()

    async def _sleep(self):
        """Sleep for the configured cycle interval."""
        interval = self.settings.cycle_interval_seconds
        logger.debug(f"Sleeping {interval}s until next cycle")
        await asyncio.sleep(interval)

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down...")
        self.running = False
        if self.exchange:
            await self.exchange.close()
        if self.redis:
            await self.redis.close()
        await self.alerts.send("🛑 Bot shutting down", priority="medium")
        logger.info("Shutdown complete")


async def run():
    """Entry point."""
    bot = TradingBot()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.shutdown()))

    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.shutdown()


def main():
    """CLI entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
