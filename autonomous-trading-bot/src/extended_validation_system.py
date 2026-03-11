"""
Extended Validation System for Bot Optimization & Validation Pipeline.
Implements 28-day demo trading with comprehensive performance tracking and edge case identification.

**Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10**
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import json
from loguru import logger

from src.gateio_testnet import GateIOTestnetConnector
from src.supabase_client import SupabaseStore


@dataclass
class EdgeCase:
    """Represents an identified edge case during validation."""
    category: str  # data_quality, logic_error, market_anomaly, API_failure
    description: str
    context: Dict
    timestamp: datetime
    resolution_status: str = "open"  # open, resolved, investigating
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'category': self.category,
            'description': self.description,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'resolution_status': self.resolution_status,
            'resolution_notes': self.resolution_notes
        }


@dataclass
class PerformanceSnapshot:
    """Real-time performance metrics snapshot."""
    timestamp: datetime
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_pnl: float
    rolling_7day_win_rate: float
    rolling_7day_pnl: float
    open_positions: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'total_pnl': self.total_pnl,
            'rolling_7day_win_rate': self.rolling_7day_win_rate,
            'rolling_7day_pnl': self.rolling_7day_pnl,
            'open_positions': self.open_positions
        }


@dataclass
class ValidationReport:
    """Comprehensive validation report."""
    start_date: datetime
    end_date: datetime
    duration_days: int
    
    # Demo trading results
    demo_metrics: Dict
    demo_trades: List[Dict]
    
    # Backtest comparison
    backtest_metrics: Dict
    performance_comparison: Dict
    variance_analysis: Dict
    
    # Edge cases
    edge_cases: List[EdgeCase]
    edge_case_summary: Dict
    
    # Performance tracking
    daily_snapshots: List[PerformanceSnapshot]
    
    # Recommendation
    go_no_go: str  # "GO", "NO_GO", "CONDITIONAL"
    recommendation_notes: str
    risk_assessment: Dict
    
    # Chart paths (Task 9.12)
    equity_curve_chart_path: Optional[str] = None
    performance_comparison_chart_path: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'duration_days': self.duration_days,
            'demo_metrics': self.demo_metrics,
            'demo_trades': self.demo_trades,
            'backtest_metrics': self.backtest_metrics,
            'performance_comparison': self.performance_comparison,
            'variance_analysis': self.variance_analysis,
            'edge_cases': [ec.to_dict() for ec in self.edge_cases],
            'edge_case_summary': self.edge_case_summary,
            'daily_snapshots': [ds.to_dict() for ds in self.daily_snapshots],
            'go_no_go': self.go_no_go,
            'recommendation_notes': self.recommendation_notes,
            'risk_assessment': self.risk_assessment,
            'equity_curve_chart_path': self.equity_curve_chart_path,
            'performance_comparison_chart_path': self.performance_comparison_chart_path
        }


class ExtendedValidationSystem:
    """
    Extended validation system for 28-day demo trading.
    
    Features:
    - 28-day demo trading loop with real API execution
    - Real-time performance tracking and monitoring
    - Edge case identification and categorization
    - Performance comparison to backtest expectations
    - Comprehensive validation report generation
    
    **Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10**
    """
    
    def __init__(
        self,
        bot,  # TradingBot instance
        exchange: GateIOTestnetConnector,
        store: SupabaseStore,
        duration_days: int = 28
    ):
        """
        Initialize extended validation system.
        
        **Validates: Requirements 20.1, 20.2, 22.6, 22.7**
        
        Args:
            bot: TradingBot instance with optimized parameters
            exchange: GateIOTestnetConnector for demo trading
            store: SupabaseStore for persistence
            duration_days: Validation duration in days (default 28)
        """
        self.bot = bot
        self.exchange = exchange
        self.store = store
        self.duration_days = duration_days
        
        # Tracking state
        self.start_date: Optional[datetime] = None
        self.edge_cases: List[EdgeCase] = []
        self.daily_snapshots: List[PerformanceSnapshot] = []
        self.backtest_metrics: Optional[Dict] = None
        
        # Circuit breaker state (Requirement 22.6)
        self.consecutive_failures: int = 0
        self.circuit_breaker_active: bool = False
        self.circuit_breaker_triggered_at: Optional[datetime] = None
        
        logger.info(f"ExtendedValidationSystem initialized: duration={duration_days} days")
    
    async def run_validation(self, backtest_metrics: Dict) -> ValidationReport:
        """
        Execute 4-week demo trading validation.
        
        **Validates: Requirements 20.1, 20.2, 20.3**
        
        Args:
            backtest_metrics: Expected metrics from backtest for comparison
            
        Returns:
            ValidationReport with comprehensive results
        """
        logger.info("Starting extended validation (28-day demo trading)")
        
        self.start_date = datetime.now()
        self.backtest_metrics = backtest_metrics
        end_date = self.start_date + timedelta(days=self.duration_days)
        
        # Initialize tracking
        self.edge_cases = []
        self.daily_snapshots = []
        
        # Run daily operations
        current_day = 0
        while datetime.now() < end_date:
            try:
                # Daily performance tracking
                await self.track_performance()
                
                # Check for anomalies
                await self._check_for_anomalies()
                
                # Wait for next day
                await asyncio.sleep(86400)  # 24 hours
                current_day += 1
                
                logger.info(f"Completed day {current_day}/{self.duration_days}")
                
            except Exception as e:
                logger.error(f"Error during validation day {current_day}: {e}")
                self._log_edge_case(
                    category="logic_error",
                    description=f"Validation loop error: {str(e)}",
                    context={'day': current_day, 'error': str(e)}
                )
        
        # Generate final report
        logger.info("Generating final validation report")
        return await self.generate_final_report()
    
    async def track_performance(self) -> PerformanceSnapshot:
        """
        Update real-time performance metrics.
        
        **Validates: Requirements 20.4, 21.1, 21.2, 21.3, 21.4**
        
        Returns:
            PerformanceSnapshot with current metrics
        """
        try:
            # Fetch recent trades from database
            trades = self.store.get_recent_trades(n=1000)
            
            if not trades:
                logger.warning("No trades found for performance tracking")
                return self._empty_snapshot()
            
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
            losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
            
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
            
            # Profit factor
            gross_profits = sum(t.get('pnl', 0) for t in winning_trades)
            gross_losses = abs(sum(t.get('pnl', 0) for t in losing_trades))
            profit_factor = gross_profits / gross_losses if gross_losses > 0 else 0.0
            
            # Total PnL
            total_pnl = sum(t.get('pnl', 0) for t in trades)
            
            # Calculate rolling 7-day metrics
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_trades = [
                t for t in trades 
                if datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')) > seven_days_ago
            ]
            
            rolling_7day_win_rate = 0.0
            rolling_7day_pnl = 0.0
            if recent_trades:
                recent_winning = [t for t in recent_trades if t.get('pnl', 0) > 0]
                rolling_7day_win_rate = len(recent_winning) / len(recent_trades)
                rolling_7day_pnl = sum(t.get('pnl', 0) for t in recent_trades)
            
            # Get open positions
            open_positions = len(self.store.get_open_positions())
            
            # Calculate Sharpe ratio (simplified)
            sharpe_ratio = self._calculate_sharpe_ratio(trades)
            
            # Calculate max drawdown
            max_drawdown = self._calculate_max_drawdown(trades)
            
            # Create snapshot
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now(),
                total_trades=total_trades,
                win_rate=win_rate,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                total_pnl=total_pnl,
                rolling_7day_win_rate=rolling_7day_win_rate,
                rolling_7day_pnl=rolling_7day_pnl,
                open_positions=open_positions
            )
            
            # Store snapshot
            self.daily_snapshots.append(snapshot)
            
            # Persist to database
            self.store.insert_performance_metric(
                metric_type="daily_snapshot",
                value=total_pnl,
                metadata=snapshot.to_dict()
            )
            
            logger.info(
                f"Performance snapshot: trades={total_trades}, win_rate={win_rate:.2%}, "
                f"pnl=${total_pnl:.2f}, 7d_win_rate={rolling_7day_win_rate:.2%}"
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error tracking performance: {e}")
            self._log_edge_case(
                category="logic_error",
                description=f"Performance tracking error: {str(e)}",
                context={'error': str(e)}
            )
            return self._empty_snapshot()
    
    def compare_to_backtest(self, demo_metrics: Dict) -> Dict:
        """
        Compare demo performance vs backtest expectations.
        
        **Validates: Requirements 20.5, 20.6, 20.7, 20.8, 20.9**
        
        Args:
            demo_metrics: Actual demo trading metrics
            
        Returns:
            Comparison analysis with variance percentages
        """
        if not self.backtest_metrics:
            logger.warning("No backtest metrics available for comparison")
            return {}
        
        comparison = {
            'backtest': self.backtest_metrics,
            'demo': demo_metrics,
            'variance': {},
            'within_thresholds': {}
        }
        
        # Calculate variance for key metrics
        metrics_to_compare = ['win_rate', 'profit_factor', 'max_drawdown', 'sharpe_ratio']
        
        for metric in metrics_to_compare:
            backtest_val = self.backtest_metrics.get(metric, 0)
            demo_val = demo_metrics.get(metric, 0)
            
            if backtest_val != 0:
                variance_pct = ((demo_val - backtest_val) / backtest_val) * 100
            else:
                variance_pct = 0.0
            
            comparison['variance'][metric] = variance_pct
            
            # Check thresholds (Requirements 20.7, 20.8, 20.9)
            if metric == 'win_rate':
                within_threshold = abs(variance_pct) <= 10.0
            elif metric == 'profit_factor':
                within_threshold = abs(variance_pct) <= 20.0
            elif metric == 'max_drawdown':
                within_threshold = variance_pct <= 5.0  # Demo can be worse but not by >5%
            else:
                within_threshold = abs(variance_pct) <= 20.0
            
            comparison['within_thresholds'][metric] = within_threshold
        
        # Overall assessment
        all_within_thresholds = all(comparison['within_thresholds'].values())
        comparison['overall_assessment'] = 'PASS' if all_within_thresholds else 'FAIL'
        
        logger.info(
            f"Backtest comparison: {comparison['overall_assessment']} - "
            f"win_rate_var={comparison['variance'].get('win_rate', 0):.1f}%, "
            f"pf_var={comparison['variance'].get('profit_factor', 0):.1f}%"
        )
        
        return comparison
    
    def identify_edge_cases(self) -> List[EdgeCase]:
        """
        Identify and categorize edge cases.
        
        **Validates: Requirements 20.10, 22.1, 22.2, 22.3, 22.4**
        
        Returns:
            List of identified edge cases
        """
        logger.info(f"Identified {len(self.edge_cases)} edge cases during validation")
        
        # Categorize edge cases (Requirement 22.2, 22.4)
        categories = {}
        for ec in self.edge_cases:
            categories[ec.category] = categories.get(ec.category, 0) + 1
        
        logger.info(f"Edge case breakdown: {categories}")
        
        return self.edge_cases
    
    def record_trade_result(self, trade: Dict) -> None:
        """
        Record trade result and check circuit breaker.
        
        **Validates: Requirements 22.6, 22.7**
        
        Args:
            trade: Trade dictionary with 'pnl' field
        """
        pnl = trade.get('pnl', 0)
        
        # Check if trade failed (negative PnL)
        if pnl < 0:
            self.consecutive_failures += 1
            logger.warning(f"Trade failed: consecutive_failures={self.consecutive_failures}")
            
            # Check circuit breaker threshold (Requirement 22.6)
            if self.consecutive_failures >= 3 and not self.circuit_breaker_active:
                self._trigger_circuit_breaker()
        else:
            # Reset counter on successful trade
            self.consecutive_failures = 0
            if self.circuit_breaker_active:
                logger.info("Successful trade recorded, but circuit breaker still active")
    
    def _trigger_circuit_breaker(self) -> None:
        """
        Trigger circuit breaker to pause trading.
        
        **Validates: Requirements 22.6, 22.7**
        """
        self.circuit_breaker_active = True
        self.circuit_breaker_triggered_at = datetime.now()
        
        # Log edge case (Requirement 22.1, 22.2)
        self._log_edge_case(
            category="logic_error",
            description="Circuit breaker triggered: 3 consecutive failed trades",
            context={
                'consecutive_failures': self.consecutive_failures,
                'triggered_at': self.circuit_breaker_triggered_at.isoformat()
            }
        )
        
        # Send alert (Requirement 22.7)
        logger.critical(
            f"CIRCUIT BREAKER TRIGGERED: 3 consecutive failed trades. "
            f"Trading paused. Manual review required before resuming."
        )
        
        # In production, this would send email/SMS/Slack alert
        # For now, we log critically
    
    def reset_circuit_breaker(self, manual_review_notes: str) -> None:
        """
        Reset circuit breaker after manual review.
        
        **Validates: Requirements 22.7**
        
        Args:
            manual_review_notes: Notes from manual review
        """
        if not self.circuit_breaker_active:
            logger.warning("Circuit breaker not active, nothing to reset")
            return
        
        self.circuit_breaker_active = False
        self.consecutive_failures = 0
        
        logger.info(f"Circuit breaker reset after manual review: {manual_review_notes}")
        
        # Update edge case resolution
        for ec in reversed(self.edge_cases):
            if ec.category == "logic_error" and "Circuit breaker" in ec.description:
                ec.resolution_status = "resolved"
                ec.resolution_notes = f"Manual review completed: {manual_review_notes}"
                break
    
    def is_trading_paused(self) -> bool:
        """
        Check if trading is paused by circuit breaker.
        
        **Validates: Requirements 22.6**
        
        Returns:
            True if circuit breaker is active
        """
        return self.circuit_breaker_active
    
    async def generate_final_report(self) -> ValidationReport:
        """
        Generate comprehensive validation report.
        
        **Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8**
        
        Returns:
            ValidationReport with all results and recommendations
        """
        logger.info("Generating comprehensive validation report")
        
        # Fetch all demo trades
        demo_trades = self.store.get_recent_trades(n=10000)
        
        # Calculate demo metrics
        demo_metrics = self._calculate_demo_metrics(demo_trades)
        
        # Compare to backtest (Task 9.13)
        performance_comparison = self.compare_to_backtest(demo_metrics)
        
        # Analyze variance
        variance_analysis = self._analyze_variance(performance_comparison)
        
        # Summarize edge cases
        edge_case_summary = self._summarize_edge_cases()
        
        # Generate recommendation
        go_no_go, recommendation_notes = self._generate_recommendation(
            demo_metrics,
            performance_comparison,
            edge_case_summary
        )
        
        # Risk assessment
        risk_assessment = self._assess_risk(demo_metrics, edge_case_summary)
        
        # Generate charts (Task 9.12)
        equity_curve_path = self._generate_equity_curve_chart(demo_trades)
        comparison_chart_path = self._generate_performance_comparison_chart(
            self.backtest_metrics or {},
            demo_metrics
        )
        
        # Create report
        report = ValidationReport(
            start_date=self.start_date,
            end_date=datetime.now(),
            duration_days=self.duration_days,
            demo_metrics=demo_metrics,
            demo_trades=demo_trades,
            backtest_metrics=self.backtest_metrics or {},
            performance_comparison=performance_comparison,
            variance_analysis=variance_analysis,
            edge_cases=self.edge_cases,
            edge_case_summary=edge_case_summary,
            daily_snapshots=self.daily_snapshots,
            go_no_go=go_no_go,
            recommendation_notes=recommendation_notes,
            risk_assessment=risk_assessment,
            equity_curve_chart_path=equity_curve_path,
            performance_comparison_chart_path=comparison_chart_path
        )
        
        # Save report to file (Task 9.14)
        self._save_report_to_file(report)
        
        # Save report to database (Task 9.14)
        self._save_report_to_database(report)
        
        logger.info(
            f"Validation report complete: {go_no_go} - "
            f"trades={demo_metrics.get('total_trades', 0)}, "
            f"win_rate={demo_metrics.get('win_rate', 0):.2%}"
        )
        
        return report
    
    # Private helper methods
    
    def _log_edge_case(
        self,
        category: str,
        description: str,
        context: Dict,
        resolution_status: str = "open"
    ) -> None:
        """
        Log an edge case.
        
        **Validates: Requirements 22.1, 22.2, 22.3**
        
        Args:
            category: One of: data_quality, logic_error, market_anomaly, API_failure
            description: Human-readable description
            context: Additional context dictionary
            resolution_status: Status (open, resolved, investigating)
        """
        # Validate category (Requirement 22.2)
        valid_categories = ['data_quality', 'logic_error', 'market_anomaly', 'API_failure']
        if category not in valid_categories:
            logger.error(f"Invalid edge case category: {category}. Must be one of {valid_categories}")
            category = 'logic_error'  # Default fallback
        
        edge_case = EdgeCase(
            category=category,
            description=description,
            context=context,
            timestamp=datetime.now(),
            resolution_status=resolution_status
        )
        
        self.edge_cases.append(edge_case)
        
        # Persist to database (Requirement 22.3)
        try:
            # Store in edge_cases table
            self.store.client.table('edge_cases').insert({
                'category': edge_case.category,
                'description': edge_case.description,
                'context': edge_case.context,
                'timestamp': edge_case.timestamp.isoformat(),
                'resolution_status': edge_case.resolution_status,
                'resolution_notes': edge_case.resolution_notes
            }).execute()
            
            logger.warning(
                f"Edge case logged: {category} - {description} "
                f"(total: {len(self.edge_cases)})"
            )
        except Exception as e:
            logger.error(f"Failed to persist edge case to database: {e}")
            # Still keep in memory even if DB fails
    
    async def _check_for_anomalies(self) -> None:
        """Check for performance anomalies and alert if needed."""
        if not self.daily_snapshots:
            return
        
        latest = self.daily_snapshots[-1]
        
        # Check rolling 7-day win rate (Requirement 21.5)
        if latest.rolling_7day_win_rate < 0.40:
            logger.warning(
                f"ALERT: Rolling 7-day win rate dropped to {latest.rolling_7day_win_rate:.2%}"
            )
            self._log_edge_case(
                category="market_anomaly",
                description=f"Win rate below 40%: {latest.rolling_7day_win_rate:.2%}",
                context={'win_rate': latest.rolling_7day_win_rate}
            )
        
        # Check rolling 7-day drawdown (Requirement 21.6)
        if latest.max_drawdown > 0.15:
            logger.warning(
                f"ALERT: Rolling 7-day drawdown exceeded 15%: {latest.max_drawdown:.2%}"
            )
            self._log_edge_case(
                category="market_anomaly",
                description=f"Drawdown exceeded 15%: {latest.max_drawdown:.2%}",
                context={'max_drawdown': latest.max_drawdown}
            )
    
    def _calculate_sharpe_ratio(self, trades: List[Dict]) -> float:
        """Calculate Sharpe ratio from trades."""
        if not trades:
            return 0.0
        
        # Extract PnL values
        pnls = [t.get('pnl', 0) for t in trades]
        
        if len(pnls) < 2:
            return 0.0
        
        # Calculate daily returns (simplified)
        mean_return = sum(pnls) / len(pnls)
        std_return = (sum((p - mean_return) ** 2 for p in pnls) / len(pnls)) ** 0.5
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe (assuming 252 trading days)
        sharpe = (mean_return / std_return) * (252 ** 0.5)
        
        return sharpe
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calculate maximum drawdown from trades."""
        if not trades:
            return 0.0
        
        # Build equity curve
        equity = 10000.0  # Starting equity
        equity_curve = [equity]
        
        for trade in trades:
            equity += trade.get('pnl', 0)
            equity_curve.append(equity)
        
        # Calculate drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def _calculate_demo_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate comprehensive metrics from demo trades."""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'total_pnl': 0.0,
                'avg_r_multiple': 0.0
            }
        
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        gross_profits = sum(t.get('pnl', 0) for t in winning_trades)
        gross_losses = abs(sum(t.get('pnl', 0) for t in losing_trades))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else 0.0
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        
        sharpe_ratio = self._calculate_sharpe_ratio(trades)
        max_drawdown = self._calculate_max_drawdown(trades)
        
        r_multiples = [t.get('r_multiple', 0) for t in trades if t.get('r_multiple')]
        avg_r_multiple = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_pnl': total_pnl,
            'avg_r_multiple': avg_r_multiple
        }
    
    def _analyze_variance(self, comparison: Dict) -> Dict:
        """Analyze variance between backtest and demo."""
        variance = comparison.get('variance', {})
        within_thresholds = comparison.get('within_thresholds', {})
        
        analysis = {
            'significant_variances': [],
            'acceptable_variances': [],
            'overall_status': comparison.get('overall_assessment', 'UNKNOWN')
        }
        
        for metric, var_pct in variance.items():
            if not within_thresholds.get(metric, False):
                analysis['significant_variances'].append({
                    'metric': metric,
                    'variance_pct': var_pct
                })
            else:
                analysis['acceptable_variances'].append({
                    'metric': metric,
                    'variance_pct': var_pct
                })
        
        return analysis
    
    def _summarize_edge_cases(self) -> Dict:
        """Summarize edge cases by category and status."""
        summary = {
            'total_count': len(self.edge_cases),
            'by_category': {},
            'by_status': {},
            'resolution_rate': 0.0
        }
        
        for ec in self.edge_cases:
            # By category
            summary['by_category'][ec.category] = summary['by_category'].get(ec.category, 0) + 1
            
            # By status
            summary['by_status'][ec.resolution_status] = summary['by_status'].get(ec.resolution_status, 0) + 1
        
        # Calculate resolution rate
        resolved = summary['by_status'].get('resolved', 0)
        if summary['total_count'] > 0:
            summary['resolution_rate'] = resolved / summary['total_count']
        
        return summary
    
    def _generate_recommendation(
        self,
        demo_metrics: Dict,
        performance_comparison: Dict,
        edge_case_summary: Dict
    ) -> tuple[str, str]:
        """Generate go/no-go recommendation."""
        # Check criteria (Requirement 24.7)
        performance_ok = performance_comparison.get('overall_assessment') == 'PASS'
        edge_cases_ok = edge_case_summary.get('resolution_rate', 0) > 0.90
        min_trades_ok = demo_metrics.get('total_trades', 0) >= 50
        
        if performance_ok and edge_cases_ok and min_trades_ok:
            return "GO", "All validation criteria met. Ready for live deployment."
        elif performance_ok and min_trades_ok:
            return "CONDITIONAL", "Performance acceptable but edge cases need review."
        else:
            reasons = []
            if not performance_ok:
                reasons.append("Performance variance exceeds thresholds")
            if not edge_cases_ok:
                reasons.append(f"Edge case resolution rate: {edge_case_summary.get('resolution_rate', 0):.1%}")
            if not min_trades_ok:
                reasons.append(f"Insufficient trades: {demo_metrics.get('total_trades', 0)}")
            
            return "NO_GO", f"Validation failed: {'; '.join(reasons)}"
    
    def _assess_risk(self, demo_metrics: Dict, edge_case_summary: Dict) -> Dict:
        """Assess risk for live deployment."""
        return {
            'risk_level': self._determine_risk_level(demo_metrics, edge_case_summary),
            'recommended_starting_capital': self._recommend_capital(demo_metrics),
            'recommended_position_limits': self._recommend_position_limits(demo_metrics),
            'key_risks': self._identify_key_risks(demo_metrics, edge_case_summary)
        }
    
    def _determine_risk_level(self, demo_metrics: Dict, edge_case_summary: Dict) -> str:
        """Determine overall risk level."""
        win_rate = demo_metrics.get('win_rate', 0)
        max_dd = demo_metrics.get('max_drawdown', 0)
        edge_case_count = edge_case_summary.get('total_count', 0)
        
        if win_rate > 0.55 and max_dd < 0.10 and edge_case_count < 5:
            return "LOW"
        elif win_rate > 0.50 and max_dd < 0.15 and edge_case_count < 10:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _recommend_capital(self, demo_metrics: Dict) -> float:
        """Recommend starting capital based on performance."""
        max_dd = demo_metrics.get('max_drawdown', 0.15)
        
        # Conservative: 3x max drawdown buffer
        min_capital = 10000.0 / (1 - max_dd * 3)
        
        return round(min_capital, 2)
    
    def _recommend_position_limits(self, demo_metrics: Dict) -> Dict:
        """Recommend position size limits."""
        return {
            'max_single_position_pct': 0.10,  # 10% per position
            'max_portfolio_exposure_pct': 0.50,  # 50% total exposure
            'max_daily_loss_pct': 0.05  # 5% daily loss limit
        }
    
    def _identify_key_risks(self, demo_metrics: Dict, edge_case_summary: Dict) -> List[str]:
        """Identify key risks for live deployment."""
        risks = []
        
        if demo_metrics.get('win_rate', 0) < 0.50:
            risks.append("Win rate below 50%")
        
        if demo_metrics.get('max_drawdown', 0) > 0.15:
            risks.append("High drawdown risk")
        
        if edge_case_summary.get('total_count', 0) > 10:
            risks.append("Multiple edge cases identified")
        
        if demo_metrics.get('total_trades', 0) < 50:
            risks.append("Limited trade sample size")
        
        return risks
    
    def _empty_snapshot(self) -> PerformanceSnapshot:
        """Create empty performance snapshot."""
        return PerformanceSnapshot(
            timestamp=datetime.now(),
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            total_pnl=0.0,
            rolling_7day_win_rate=0.0,
            rolling_7day_pnl=0.0,
            open_positions=0
        )
    
    def _generate_equity_curve_chart(self, trades: List[Dict]) -> Optional[str]:
        """
        Generate equity curve chart from trades.
        
        **Validates: Requirements 24.5 (Task 9.12)**
        
        Args:
            trades: List of trade dictionaries
            
        Returns:
            Path to saved chart file
        """
        if not trades:
            logger.warning("No trades available for equity curve chart")
            return None
        
        try:
            # Build equity curve
            equity = 10000.0  # Starting equity
            timestamps = [self.start_date]
            equity_values = [equity]
            
            for trade in sorted(trades, key=lambda t: t.get('created_at', '')):
                equity += trade.get('pnl', 0)
                try:
                    timestamp = datetime.fromisoformat(trade['created_at'].replace('Z', '+00:00'))
                    timestamps.append(timestamp)
                    equity_values.append(equity)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping trade with invalid timestamp: {e}")
                    continue
            
            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Plot equity curve
            ax.plot(timestamps, equity_values, linewidth=2, color='#2E86AB', label='Equity Curve')
            
            # Add horizontal line at starting equity
            ax.axhline(y=10000, color='gray', linestyle='--', alpha=0.5, label='Starting Equity')
            
            # Formatting
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Equity ($)', fontsize=12)
            ax.set_title('Demo Trading Equity Curve', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            
            # Tight layout
            plt.tight_layout()
            
            # Save chart
            output_dir = Path('./reports/charts')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            chart_path = output_dir / f'equity_curve_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Equity curve chart saved to: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"Error generating equity curve chart: {e}")
            return None
    
    def _generate_performance_comparison_chart(
        self,
        backtest_metrics: Dict,
        demo_metrics: Dict
    ) -> Optional[str]:
        """
        Generate performance comparison chart.
        
        **Validates: Requirements 24.4, 24.5 (Task 9.12)**
        
        Args:
            backtest_metrics: Backtest performance metrics
            demo_metrics: Demo trading performance metrics
            
        Returns:
            Path to saved chart file
        """
        if not backtest_metrics or not demo_metrics:
            logger.warning("Insufficient metrics for comparison chart")
            return None
        
        try:
            # Metrics to compare
            metrics = ['win_rate', 'profit_factor', 'sharpe_ratio', 'max_drawdown']
            metric_labels = ['Win Rate', 'Profit Factor', 'Sharpe Ratio', 'Max Drawdown']
            
            backtest_values = [backtest_metrics.get(m, 0) for m in metrics]
            demo_values = [demo_metrics.get(m, 0) for m in metrics]
            
            # Create figure with subplots
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            axes = axes.flatten()
            
            for idx, (metric, label) in enumerate(zip(metrics, metric_labels)):
                ax = axes[idx]
                
                bt_val = backtest_metrics.get(metric, 0)
                demo_val = demo_metrics.get(metric, 0)
                
                # Bar chart
                x = ['Backtest', 'Demo']
                values = [bt_val, demo_val]
                colors = ['#2E86AB', '#A23B72']
                
                bars = ax.bar(x, values, color=colors, alpha=0.7, edgecolor='black')
                
                # Add value labels on bars
                for bar in bars:
                    height = bar.get_height()
                    ax.text(
                        bar.get_x() + bar.get_width() / 2.,
                        height,
                        f'{height:.3f}',
                        ha='center',
                        va='bottom',
                        fontsize=10
                    )
                
                # Calculate variance
                if bt_val != 0:
                    variance_pct = ((demo_val - bt_val) / bt_val) * 100
                    ax.set_title(f'{label}\nVariance: {variance_pct:+.1f}%', fontsize=11, fontweight='bold')
                else:
                    ax.set_title(label, fontsize=11, fontweight='bold')
                
                ax.set_ylabel('Value', fontsize=10)
                ax.grid(True, alpha=0.3, axis='y')
            
            # Overall title
            fig.suptitle('Backtest vs Demo Performance Comparison', fontsize=16, fontweight='bold', y=0.995)
            
            # Tight layout
            plt.tight_layout()
            
            # Save chart
            output_dir = Path('./reports/charts')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            chart_path = output_dir / f'performance_comparison_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Performance comparison chart saved to: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"Error generating performance comparison chart: {e}")
            return None
    
    def _save_report_to_file(self, report: ValidationReport) -> None:
        """
        Save validation report to JSON file.
        
        **Validates: Requirements 24.1, 24.8 (Task 9.14)**
        
        Args:
            report: ValidationReport to save
        """
        try:
            # Create reports directory
            output_dir = Path('./reports')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            filename = f'validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            filepath = output_dir / filename
            
            # Convert report to dict and save
            report_dict = report.to_dict()
            
            with open(filepath, 'w') as f:
                json.dump(report_dict, f, indent=2, default=str)
            
            logger.info(f"Validation report saved to file: {filepath}")
            
            # Also save a human-readable summary
            summary_path = output_dir / f'validation_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            self._save_human_readable_summary(report, summary_path)
            
        except Exception as e:
            logger.error(f"Error saving report to file: {e}")
    
    def _save_human_readable_summary(self, report: ValidationReport, filepath: Path) -> None:
        """
        Save human-readable summary of validation report.
        
        **Validates: Requirements 24.1 (Task 9.14)**
        
        Args:
            report: ValidationReport to summarize
            filepath: Path to save summary
        """
        try:
            with open(filepath, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("VALIDATION REPORT SUMMARY\n")
                f.write("=" * 80 + "\n\n")
                
                # Executive Summary
                f.write("EXECUTIVE SUMMARY\n")
                f.write("-" * 80 + "\n")
                f.write(f"Validation Period: {report.start_date.strftime('%Y-%m-%d')} to {report.end_date.strftime('%Y-%m-%d')}\n")
                f.write(f"Duration: {report.duration_days} days\n")
                f.write(f"Recommendation: {report.go_no_go}\n")
                f.write(f"Notes: {report.recommendation_notes}\n\n")
                
                # Backtest Results
                f.write("BACKTEST RESULTS\n")
                f.write("-" * 80 + "\n")
                for key, value in report.backtest_metrics.items():
                    if isinstance(value, float):
                        f.write(f"{key}: {value:.4f}\n")
                    else:
                        f.write(f"{key}: {value}\n")
                f.write("\n")
                
                # Demo Trading Results
                f.write("DEMO TRADING RESULTS\n")
                f.write("-" * 80 + "\n")
                for key, value in report.demo_metrics.items():
                    if isinstance(value, float):
                        f.write(f"{key}: {value:.4f}\n")
                    else:
                        f.write(f"{key}: {value}\n")
                f.write("\n")
                
                # Performance Comparison
                f.write("PERFORMANCE COMPARISON\n")
                f.write("-" * 80 + "\n")
                variance = report.variance_analysis.get('variance', {})
                for metric, var_pct in variance.items():
                    f.write(f"{metric}: {var_pct:+.2f}%\n")
                f.write(f"\nOverall Status: {report.variance_analysis.get('overall_status', 'UNKNOWN')}\n\n")
                
                # Edge Cases Summary
                f.write("EDGE CASES SUMMARY\n")
                f.write("-" * 80 + "\n")
                f.write(f"Total: {report.edge_case_summary.get('total_count', 0)}\n")
                f.write(f"Resolution Rate: {report.edge_case_summary.get('resolution_rate', 0):.1%}\n")
                f.write("\nBy Category:\n")
                for category, count in report.edge_case_summary.get('by_category', {}).items():
                    f.write(f"  {category}: {count}\n")
                f.write("\n")
                
                # Risk Assessment
                f.write("RISK ASSESSMENT\n")
                f.write("-" * 80 + "\n")
                f.write(f"Risk Level: {report.risk_assessment.get('risk_level', 'UNKNOWN')}\n")
                f.write(f"Recommended Starting Capital: ${report.risk_assessment.get('recommended_starting_capital', 0):,.2f}\n")
                f.write("\nPosition Limits:\n")
                for key, value in report.risk_assessment.get('recommended_position_limits', {}).items():
                    if isinstance(value, float):
                        f.write(f"  {key}: {value:.1%}\n")
                    else:
                        f.write(f"  {key}: {value}\n")
                f.write("\nKey Risks:\n")
                for risk in report.risk_assessment.get('key_risks', []):
                    f.write(f"  - {risk}\n")
                f.write("\n")
                
                # Charts
                if report.equity_curve_chart_path:
                    f.write(f"Equity Curve Chart: {report.equity_curve_chart_path}\n")
                if report.performance_comparison_chart_path:
                    f.write(f"Performance Comparison Chart: {report.performance_comparison_chart_path}\n")
                
                f.write("\n" + "=" * 80 + "\n")
            
            logger.info(f"Human-readable summary saved to: {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving human-readable summary: {e}")
    
    def _save_report_to_database(self, report: ValidationReport) -> None:
        """
        Save validation report to database.
        
        **Validates: Requirements 24.8 (Task 9.14)**
        
        Args:
            report: ValidationReport to save
        """
        try:
            # Save to validation_reports table
            report_data = {
                'start_date': report.start_date.isoformat(),
                'end_date': report.end_date.isoformat(),
                'duration_days': report.duration_days,
                'demo_metrics': report.demo_metrics,
                'backtest_metrics': report.backtest_metrics,
                'performance_comparison': report.performance_comparison,
                'variance_analysis': report.variance_analysis,
                'edge_case_summary': report.edge_case_summary,
                'go_no_go': report.go_no_go,
                'recommendation_notes': report.recommendation_notes,
                'risk_assessment': report.risk_assessment,
                'equity_curve_chart_path': report.equity_curve_chart_path,
                'performance_comparison_chart_path': report.performance_comparison_chart_path,
                'created_at': datetime.now().isoformat()
            }
            
            # Insert into database
            self.store.client.table('validation_reports').insert(report_data).execute()
            
            logger.info("Validation report saved to database")
            
        except Exception as e:
            logger.error(f"Error saving report to database: {e}")
            # Don't fail if database save fails - report is already saved to file
