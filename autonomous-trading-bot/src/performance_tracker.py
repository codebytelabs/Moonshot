"""
Performance Tracker Module.
Tracks rolling 7-day metrics, updates database, generates reports, and implements alerts.

Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 21.7, 21.8
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pandas as pd
from loguru import logger

try:
    from .supabase_client import SupabaseStore
except ImportError:
    # For testing without package context
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from supabase_client import SupabaseStore


class PerformanceTracker:
    """
    Tracks trading performance with rolling 7-day metrics and alerts.
    
    Features:
    - Rolling 7-day metrics: win_rate, profit_factor, avg_R_multiple, daily_PnL
    - Daily performance_metrics table updates
    - Daily summary report generation
    - Performance degradation alerts (win_rate <40%, drawdown >15%)
    - API endpoint support for current metrics
    
    Requirements:
    - 21.1: Real-time performance metric updates
    - 21.2: Daily performance_metrics table persistence
    - 21.3: Performance degradation alerts
    - 21.4: Rolling 7-day metric tracking
    - 21.5: Win rate degradation alert (<40%)
    - 21.6: Drawdown alert (>15%)
    - 21.7: Daily summary report generation
    - 21.8: API endpoint for current metrics
    """
    
    def __init__(self, store: Optional[SupabaseStore] = None):
        """
        Initialize performance tracker.
        
        Args:
            store: SupabaseStore instance for database operations
        """
        self.store = store
        self.alert_callbacks: List[callable] = []
        logger.info("Performance tracker initialized")
    
    def register_alert_callback(self, callback: callable) -> None:
        """
        Register callback function for alerts.
        
        Args:
            callback: Function to call when alert is triggered
                     Signature: callback(alert_type: str, message: str, data: Dict)
        """
        self.alert_callbacks.append(callback)
        callback_name = getattr(callback, '__name__', 'anonymous')
        logger.info(f"Registered alert callback: {callback_name}")
    
    def get_trades_in_window(
        self, 
        end_date: datetime, 
        window_days: int = 7
    ) -> List[Dict]:
        """
        Fetch trades within a rolling window.
        
        Args:
            end_date: End date of the window
            window_days: Number of days to look back (default: 7)
        
        Returns:
            List of trade records
        """
        start_date = end_date - timedelta(days=window_days)
        
        try:
            # Query trades table for closed trades in window
            result = self.store.client.table("trades").select("*").gte(
                "timestamp", start_date.isoformat()
            ).lte(
                "timestamp", end_date.isoformat()
            ).eq(
                "status", "closed"
            ).execute()
            
            trades = result.data if result.data else []
            logger.debug(f"Retrieved {len(trades)} trades in {window_days}-day window ending {end_date}")
            return trades
            
        except Exception as e:
            logger.error(f"Error fetching trades in window: {e}")
            return []
    
    def calculate_rolling_metrics(
        self, 
        end_date: datetime, 
        window_days: int = 7
    ) -> Dict:
        """
        Calculate rolling metrics for a time window.
        
        Property 42: Rolling metrics calculation
        For any 7-day window, rolling metrics (win_rate, profit_factor, 
        avg_R_multiple, daily_PnL) should be calculated using only trades 
        within that window.
        
        Args:
            end_date: End date of the window
            window_days: Number of days to look back (default: 7)
        
        Returns:
            Dict with rolling metrics:
            - win_rate: Percentage of winning trades
            - profit_factor: Gross profits / gross losses
            - avg_r_multiple: Average R-multiple across trades
            - daily_pnl: Average daily PnL
            - total_trades: Number of trades in window
            - total_pnl: Total PnL in window
        """
        trades = self.get_trades_in_window(end_date, window_days)
        
        if not trades:
            logger.warning(f"No trades found in {window_days}-day window ending {end_date}")
            return {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_r_multiple": 0.0,
                "daily_pnl": 0.0,
                "total_trades": 0,
                "total_pnl": 0.0,
                "window_start": (end_date - timedelta(days=window_days)).isoformat(),
                "window_end": end_date.isoformat()
            }
        
        # Extract PnL and R-multiples
        pnls = [float(t.get("pnl", 0)) for t in trades if t.get("pnl") is not None]
        r_multiples = [float(t.get("r_multiple", 0)) for t in trades if t.get("r_multiple") is not None]
        
        # Calculate win rate
        winning_trades = [p for p in pnls if p > 0]
        win_rate = (len(winning_trades) / len(pnls) * 100) if pnls else 0.0
        
        # Calculate profit factor
        gross_profits = sum([p for p in pnls if p > 0])
        gross_losses = abs(sum([p for p in pnls if p < 0]))
        profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else 0.0
        
        # Calculate average R-multiple
        avg_r_multiple = (sum(r_multiples) / len(r_multiples)) if r_multiples else 0.0
        
        # Calculate daily PnL
        total_pnl = sum(pnls)
        daily_pnl = total_pnl / window_days if window_days > 0 else 0.0
        
        metrics = {
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_r_multiple": round(avg_r_multiple, 2),
            "daily_pnl": round(daily_pnl, 2),
            "total_trades": len(trades),
            "total_pnl": round(total_pnl, 2),
            "window_start": (end_date - timedelta(days=window_days)).isoformat(),
            "window_end": end_date.isoformat()
        }
        
        logger.info(f"Rolling metrics calculated: {metrics}")
        return metrics
    
    def calculate_drawdown(
        self, 
        end_date: datetime, 
        window_days: int = 7
    ) -> float:
        """
        Calculate maximum drawdown in the window.
        
        Args:
            end_date: End date of the window
            window_days: Number of days to look back
        
        Returns:
            Maximum drawdown percentage (positive value)
        """
        trades = self.get_trades_in_window(end_date, window_days)
        
        if not trades:
            return 0.0
        
        # Sort trades by timestamp
        trades_sorted = sorted(trades, key=lambda t: t.get("timestamp", ""))
        
        # Build equity curve
        equity = 10000.0  # Starting equity
        equity_curve = [equity]
        
        for trade in trades_sorted:
            pnl = float(trade.get("pnl", 0))
            equity += pnl
            equity_curve.append(equity)
        
        # Calculate drawdown
        peak = equity_curve[0]
        max_drawdown = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = ((peak - value) / peak * 100) if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)
        
        logger.debug(f"Calculated drawdown: {max_drawdown:.2f}%")
        return round(max_drawdown, 2)
    
    def check_alerts(self, metrics: Dict, drawdown: float) -> List[Dict]:
        """
        Check for performance degradation and trigger alerts.
        
        Property 43: Performance degradation alert
        For any 7-day rolling window, if win_rate drops below 40%, 
        an alert should be triggered.
        
        Property 44: Drawdown alert
        For any 7-day rolling window, if drawdown exceeds 15%, 
        an alert should be triggered.
        
        Args:
            metrics: Rolling metrics dict
            drawdown: Current drawdown percentage
        
        Returns:
            List of triggered alerts
        """
        alerts = []
        
        # Check win rate degradation (Requirement 21.5)
        if metrics["win_rate"] < 40.0 and metrics["total_trades"] >= 10:
            alert = {
                "type": "win_rate_degradation",
                "severity": "warning",
                "message": f"Win rate dropped to {metrics['win_rate']:.2f}% (threshold: 40%)",
                "data": {
                    "win_rate": metrics["win_rate"],
                    "threshold": 40.0,
                    "total_trades": metrics["total_trades"],
                    "window": f"{metrics['window_start']} to {metrics['window_end']}"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            alerts.append(alert)
            logger.warning(f"ALERT: {alert['message']}")
            
            # Trigger callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert["type"], alert["message"], alert["data"])
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
        
        # Check drawdown alert (Requirement 21.6)
        if drawdown > 15.0:
            alert = {
                "type": "drawdown_exceeded",
                "severity": "critical",
                "message": f"Drawdown exceeded {drawdown:.2f}% (threshold: 15%)",
                "data": {
                    "drawdown": drawdown,
                    "threshold": 15.0,
                    "total_trades": metrics["total_trades"],
                    "window": f"{metrics['window_start']} to {metrics['window_end']}"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            alerts.append(alert)
            logger.critical(f"ALERT: {alert['message']}")
            
            # Trigger callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert["type"], alert["message"], alert["data"])
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
        
        return alerts
    
    def update_performance_metrics_table(
        self, 
        date: datetime, 
        metrics: Dict
    ) -> bool:
        """
        Update performance_metrics table with daily metrics.
        
        Requirement 21.2: Daily performance_metrics table persistence
        
        Args:
            date: Date for the metrics
            metrics: Metrics dict to persist
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare record for database
            record = {
                "date": date.date().isoformat(),
                "total_trades": metrics["total_trades"],
                "win_rate": Decimal(str(metrics["win_rate"])),
                "profit_factor": Decimal(str(metrics["profit_factor"])),
                "avg_r_multiple": Decimal(str(metrics["avg_r_multiple"])),
                "daily_pnl": Decimal(str(metrics["daily_pnl"])),
                "total_pnl": Decimal(str(metrics["total_pnl"])),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Check if record exists for this date
            existing = self.store.client.table("performance_metrics").select("id").eq(
                "date", record["date"]
            ).execute()
            
            if existing.data:
                # Update existing record
                result = self.store.client.table("performance_metrics").update(
                    record
                ).eq("date", record["date"]).execute()
                logger.info(f"Updated performance metrics for {record['date']}")
            else:
                # Insert new record
                result = self.store.client.table("performance_metrics").insert(
                    record
                ).execute()
                logger.info(f"Inserted performance metrics for {record['date']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating performance_metrics table: {e}")
            return False
    
    def generate_daily_summary(
        self, 
        date: datetime
    ) -> Dict:
        """
        Generate daily summary report.
        
        Requirement 21.7: Daily summary report generation
        
        Args:
            date: Date for the summary
        
        Returns:
            Dict with daily summary including:
            - trades_executed: Number of trades
            - open_positions: Current open positions
            - daily_pnl: PnL for the day
            - rolling_7day_metrics: 7-day rolling metrics
            - alerts: Any triggered alerts
        """
        logger.info(f"Generating daily summary for {date.date()}")
        
        # Get trades for the day
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        daily_trades = self.get_trades_in_window(day_end, window_days=1)
        
        # Calculate daily PnL
        daily_pnl = sum([float(t.get("pnl", 0)) for t in daily_trades if t.get("pnl") is not None])
        
        # Get open positions
        try:
            open_positions_result = self.store.client.table("positions").select("*").eq(
                "status", "open"
            ).execute()
            open_positions = open_positions_result.data if open_positions_result.data else []
        except Exception as e:
            logger.error(f"Error fetching open positions: {e}")
            open_positions = []
        
        # Calculate rolling 7-day metrics
        rolling_metrics = self.calculate_rolling_metrics(date, window_days=7)
        drawdown = self.calculate_drawdown(date, window_days=7)
        
        # Check for alerts
        alerts = self.check_alerts(rolling_metrics, drawdown)
        
        # Build summary
        summary = {
            "date": date.date().isoformat(),
            "trades_executed": len(daily_trades),
            "open_positions": len(open_positions),
            "daily_pnl": round(daily_pnl, 2),
            "rolling_7day_metrics": rolling_metrics,
            "drawdown_7day": drawdown,
            "alerts": alerts,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Daily summary generated: {summary}")
        return summary
    
    def get_current_metrics(self) -> Dict:
        """
        Get current performance metrics for API endpoint.
        
        Requirement 21.8: API endpoint for current metrics
        
        Returns:
            Dict with current metrics including:
            - rolling_7day: 7-day rolling metrics
            - rolling_30day: 30-day rolling metrics
            - all_time: All-time metrics
            - equity_curve: Recent equity curve data
        """
        now = datetime.now(timezone.utc)
        
        # Calculate rolling metrics
        metrics_7day = self.calculate_rolling_metrics(now, window_days=7)
        metrics_30day = self.calculate_rolling_metrics(now, window_days=30)
        
        # Get all-time trades
        try:
            all_trades_result = self.store.client.table("trades").select("*").eq(
                "status", "closed"
            ).execute()
            all_trades = all_trades_result.data if all_trades_result.data else []
        except Exception as e:
            logger.error(f"Error fetching all trades: {e}")
            all_trades = []
        
        # Calculate all-time metrics
        if all_trades:
            pnls = [float(t.get("pnl", 0)) for t in all_trades if t.get("pnl") is not None]
            r_multiples = [float(t.get("r_multiple", 0)) for t in all_trades if t.get("r_multiple") is not None]
            
            winning_trades = [p for p in pnls if p > 0]
            all_time_win_rate = (len(winning_trades) / len(pnls) * 100) if pnls else 0.0
            
            gross_profits = sum([p for p in pnls if p > 0])
            gross_losses = abs(sum([p for p in pnls if p < 0]))
            all_time_profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else 0.0
            
            all_time_avg_r = (sum(r_multiples) / len(r_multiples)) if r_multiples else 0.0
            all_time_total_pnl = sum(pnls)
        else:
            all_time_win_rate = 0.0
            all_time_profit_factor = 0.0
            all_time_avg_r = 0.0
            all_time_total_pnl = 0.0
        
        # Build equity curve (last 30 days)
        equity_curve = self._build_equity_curve(now, window_days=30)
        
        # Calculate current drawdowns
        drawdown_7day = self.calculate_drawdown(now, window_days=7)
        drawdown_30day = self.calculate_drawdown(now, window_days=30)
        
        return {
            "rolling_7day": {
                **metrics_7day,
                "drawdown": drawdown_7day
            },
            "rolling_30day": {
                **metrics_30day,
                "drawdown": drawdown_30day
            },
            "all_time": {
                "total_trades": len(all_trades),
                "win_rate": round(all_time_win_rate, 2),
                "profit_factor": round(all_time_profit_factor, 2),
                "avg_r_multiple": round(all_time_avg_r, 2),
                "total_pnl": round(all_time_total_pnl, 2)
            },
            "equity_curve": equity_curve,
            "timestamp": now.isoformat()
        }
    
    def _build_equity_curve(
        self, 
        end_date: datetime, 
        window_days: int = 30
    ) -> List[Dict]:
        """
        Build equity curve data points.
        
        Args:
            end_date: End date for the curve
            window_days: Number of days to include
        
        Returns:
            List of equity curve points with timestamp and equity
        """
        trades = self.get_trades_in_window(end_date, window_days)
        
        if not trades:
            return []
        
        # Sort trades by timestamp
        trades_sorted = sorted(trades, key=lambda t: t.get("timestamp", ""))
        
        # Build equity curve
        equity = 10000.0  # Starting equity
        curve = [{"timestamp": (end_date - timedelta(days=window_days)).isoformat(), "equity": equity}]
        
        for trade in trades_sorted:
            pnl = float(trade.get("pnl", 0))
            equity += pnl
            curve.append({
                "timestamp": trade.get("timestamp"),
                "equity": round(equity, 2)
            })
        
        return curve
    
    def track_performance_realtime(self) -> Dict:
        """
        Track performance in real-time and update metrics.
        
        Requirement 21.1: Real-time performance metric updates
        
        Returns:
            Dict with current metrics and any alerts
        """
        now = datetime.now(timezone.utc)
        
        # Calculate rolling metrics
        metrics = self.calculate_rolling_metrics(now, window_days=7)
        drawdown = self.calculate_drawdown(now, window_days=7)
        
        # Check for alerts
        alerts = self.check_alerts(metrics, drawdown)
        
        # Update database (daily)
        self.update_performance_metrics_table(now, metrics)
        
        return {
            "metrics": metrics,
            "drawdown": drawdown,
            "alerts": alerts,
            "timestamp": now.isoformat()
        }
