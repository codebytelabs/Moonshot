"""
Supabase persistence layer.
Full CRUD for all 8 tables defined in schema.sql.
"""
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from supabase import create_client, Client
from .metrics import errors_total


class SupabaseStore:
    """Supabase client with typed insert/query methods for all tables."""

    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)
        logger.info("Supabase client initialized")

    # ── Generic helpers ─────────────────────────────────────────────────

    def _insert(self, table: str, row: dict) -> Optional[dict]:
        """Insert a row, returning the inserted data or None on error."""
        try:
            result = self.client.table(table).insert(row).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Supabase insert failed ({table}): {e}")
            errors_total.labels(component="supabase", error_type="insert").inc()
            return None

    def _upsert(self, table: str, row: dict) -> Optional[dict]:
        """Upsert a row (insert or update on conflict)."""
        try:
            result = self.client.table(table).upsert(row).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Supabase upsert failed ({table}): {e}")
            errors_total.labels(component="supabase", error_type="upsert").inc()
            return None

    def _query(self, table: str, filters: Optional[dict] = None, order_by: Optional[str] = None,
               limit: Optional[int] = None, ascending: bool = False) -> list:
        """Generic query with optional filters, ordering, and limit."""
        try:
            q = self.client.table(table).select("*")
            if filters:
                for col, val in filters.items():
                    q = q.eq(col, val)
            if order_by:
                q = q.order(order_by, desc=not ascending)
            if limit:
                q = q.limit(limit)
            result = q.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Supabase query failed ({table}): {e}")
            errors_total.labels(component="supabase", error_type="query").inc()
            return []

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Watcher Signals ─────────────────────────────────────────────────

    def insert_watcher_signal(self, symbol: str, score: float, features: dict,
                              exchange: str = "gateio") -> Optional[dict]:
        return self._insert("watcher_signals", {
            "created_at": self._now(),
            "symbol": symbol,
            "exchange": exchange,
            "score": score,
            "features": features,
        })

    # ── Analyzer Signals ────────────────────────────────────────────────

    def insert_analyzer_signal(self, symbol: str, setup_type: str, ta_score: float,
                               features: dict, entry_zone: dict, exchange: str = "gateio") -> Optional[dict]:
        return self._insert("analyzer_signals", {
            "created_at": self._now(),
            "symbol": symbol,
            "exchange": exchange,
            "setup_type": setup_type,
            "ta_score": ta_score,
            "features": features,
            "entry_zone": entry_zone,
        })

    # ── Context Analysis ────────────────────────────────────────────────

    def insert_context_analysis(self, symbol: str, sentiment: str, confidence: float,
                                catalysts: list, risks: list, driver_type: str,
                                narrative_strength: float) -> Optional[dict]:
        return self._insert("context_analysis", {
            "created_at": self._now(),
            "symbol": symbol,
            "sentiment": sentiment,
            "confidence": confidence,
            "catalysts": catalysts,
            "risks": risks,
            "driver_type": driver_type,
            "narrative_strength": narrative_strength,
        })

    # ── Decisions ───────────────────────────────────────────────────────

    def insert_decision(self, symbol: str, posterior: float, action: str,
                        setup_type: str, mode: str, reasoning: dict) -> Optional[dict]:
        return self._insert("decisions", {
            "created_at": self._now(),
            "symbol": symbol,
            "posterior": posterior,
            "action": action,
            "setup_type": setup_type,
            "mode": mode,
            "reasoning": reasoning,
        })

    # ── Positions ───────────────────────────────────────────────────────

    def upsert_position(self, position_id: str, symbol: str, side: str, status: str,
                        entry_price: float, current_price: float, quantity: float,
                        notional_usd: float, unrealized_pnl: float,
                        stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
                        exchange: str = "gateio") -> Optional[dict]:
        return self._upsert("positions", {
            "id": position_id,
            "updated_at": self._now(),
            "symbol": symbol,
            "exchange": exchange,
            "side": side,
            "status": status,
            "entry_price": entry_price,
            "current_price": current_price,
            "quantity": quantity,
            "notional_usd": notional_usd,
            "unrealized_pnl": unrealized_pnl,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        })

    def get_open_positions(self) -> list:
        return self._query("positions", filters={"status": "open"})

    def get_position(self, position_id: str) -> Optional[dict]:
        rows = self._query("positions", filters={"id": position_id}, limit=1)
        return rows[0] if rows else None

    # ── Trades ──────────────────────────────────────────────────────────

    def insert_trade(self, position_id: Optional[str], symbol: str, side: str, price: float,
                     quantity: float, notional_usd: float, trade_type: str,
                     pnl: Optional[float] = None, r_multiple: Optional[float] = None,
                     exchange: str = "gateio", created_at: Optional[str] = None,
                     exchange_trade_id: Optional[str] = None) -> Optional[dict]:
        row = {
            "created_at": created_at or self._now(),
            "position_id": position_id,
            "symbol": symbol,
            "exchange": exchange,
            "side": side,
            "price": price,
            "quantity": quantity,
            "notional_usd": notional_usd,
            "trade_type": trade_type,
            "pnl": pnl,
            "r_multiple": r_multiple,
        }
        if exchange_trade_id:
            row["exchange_trade_id"] = str(exchange_trade_id)
            
        return self._insert("trades", row)

    def get_recent_trades(self, n: int = 50) -> list:
        return self._query("trades", order_by="created_at", limit=n)

    def get_latest_trade_time(self, symbol: str) -> Optional[int]:
        """Get the timestamp (ms) of the latest trade for a symbol."""
        rows = self._query("trades", filters={"symbol": symbol}, order_by="created_at", limit=1)
        if not rows:
            return None
        # Convert ISO string to timestamp ms
        dt = datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)

    # ── Performance Metrics ─────────────────────────────────────────────

    def insert_performance_metric(self, metric_type: str, value: float,
                                  metadata: Optional[dict] = None) -> Optional[dict]:
        return self._insert("performance_metrics", {
            "created_at": self._now(),
            "metric_type": metric_type,
            "value": value,
            "metadata": metadata or {},
        })

    def get_performance_history(self, days: int = 30) -> list:
        return self._query("performance_metrics", order_by="created_at", limit=days * 24)

    # ── BigBrother Events ───────────────────────────────────────────────

    def insert_bigbrother_event(self, event_type: str, severity: str,
                                message: str, details: Optional[dict] = None) -> Optional[dict]:
        return self._insert("bigbrother_events", {
            "created_at": self._now(),
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "details": details or {},
        })

    # ── User Interactions ───────────────────────────────────────────────

    def insert_user_interaction(self, interaction_type: str, content: str,
                                response: Optional[str] = None) -> Optional[dict]:
        return self._insert("user_interactions", {
            "created_at": self._now(),
            "interaction_type": interaction_type,
            "content": content,
            "response": response,
        })
