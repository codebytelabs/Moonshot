"""
Performance Metrics Calculator for Backtesting Framework.
Computes comprehensive trading performance metrics from backtest results.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8**
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class PerformanceMetrics:
    """Container for all performance metrics."""
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_r_multiple: float
    expectancy: float
    r_multiple_distribution: Dict[str, int]
    monthly_returns: pd.Series
    total_trades: int
    winning_trades: int
    losing_trades: int
    gross_profits: float
    gross_losses: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    best_month: float
    worst_month: float
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        return {
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'avg_r_multiple': self.avg_r_multiple,
            'expectancy': self.expectancy,
            'r_multiple_distribution': self.r_multiple_distribution,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'gross_profits': self.gross_profits,
            'gross_losses': self.gross_losses,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'best_month': self.best_month,
            'worst_month': self.worst_month
        }
    
    def validate_targets(self) -> Dict[str, bool]:
        """
        Validate metrics against target thresholds.
        
        **Validates: Requirement 8.9**
        
        Targets:
        - win_rate > 50%
        - profit_factor > 2.0
        - max_drawdown < 20%
        """
        return {
            'win_rate_ok': self.win_rate > 50.0,
            'profit_factor_ok': self.profit_factor > 2.0,
            'max_drawdown_ok': self.max_drawdown < 20.0
        }


class PerformanceMetricsCalculator:
    """
    Computes comprehensive performance metrics from backtest results.
    
    Features:
    - Win rate, profit factor, Sharpe ratio
    - Maximum drawdown calculation
    - R-multiple distribution analysis
    - Monthly returns breakdown
    - Expectancy calculation
    
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8**
    """
    
    def __init__(
        self,
        trades: List[Dict],
        equity_curve: pd.Series,
        risk_free_rate: float = 0.0
    ):
        """
        Initialize calculator with trade history and equity curve.
        
        Args:
            trades: List of trade dictionaries with pnl, r_multiple, etc.
            equity_curve: Time series of equity values
            risk_free_rate: Annual risk-free rate for Sharpe calculation (default 0.0)
        """
        self.trades = trades
        self.equity_curve = equity_curve
        self.risk_free_rate = risk_free_rate
        
        logger.info(
            f"PerformanceMetricsCalculator initialized with {len(trades)} trades"
        )
    
    def calculate_all_metrics(self) -> PerformanceMetrics:
        """
        Compute all performance metrics.
        
        Returns:
            PerformanceMetrics dataclass with all calculated metrics
        """
        logger.info("Calculating all performance metrics...")
        
        if len(self.trades) == 0:
            logger.warning("No trades to analyze, returning zero metrics")
            return self._zero_metrics()
        
        # Calculate individual metrics
        win_rate = self.win_rate()
        profit_factor = self.profit_factor()
        sharpe = self.sharpe_ratio()
        max_dd = self.max_drawdown()
        avg_r = self.avg_r_multiple()
        exp = self.expectancy()
        r_dist = self.r_multiple_distribution()
        monthly_ret = self.monthly_returns()
        
        # Calculate trade statistics
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]
        
        gross_profits = sum(t['pnl'] for t in winning_trades)
        gross_losses = abs(sum(t['pnl'] for t in losing_trades))
        
        avg_win = gross_profits / len(winning_trades) if winning_trades else 0.0
        avg_loss = gross_losses / len(losing_trades) if losing_trades else 0.0
        
        largest_win = max((t['pnl'] for t in winning_trades), default=0.0)
        largest_loss = min((t['pnl'] for t in losing_trades), default=0.0)
        
        best_month = monthly_ret.max() if len(monthly_ret) > 0 else 0.0
        worst_month = monthly_ret.min() if len(monthly_ret) > 0 else 0.0
        
        metrics = PerformanceMetrics(
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            avg_r_multiple=avg_r,
            expectancy=exp,
            r_multiple_distribution=r_dist,
            monthly_returns=monthly_ret,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            gross_profits=gross_profits,
            gross_losses=gross_losses,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            best_month=best_month,
            worst_month=worst_month
        )
        
        logger.info(
            f"Metrics calculated: win_rate={win_rate:.2f}%, "
            f"profit_factor={profit_factor:.2f}, sharpe={sharpe:.2f}, "
            f"max_dd={max_dd:.2f}%"
        )
        
        return metrics
    
    def win_rate(self) -> float:
        """
        Calculate win rate as percentage of winning trades.
        
        **Validates: Requirement 8.1**
        
        Formula: (winning_trades / total_trades) * 100
        
        Returns:
            Win rate as percentage (0-100)
        """
        if len(self.trades) == 0:
            return 0.0
        
        winning_trades = len([t for t in self.trades if t['pnl'] > 0])
        win_rate = (winning_trades / len(self.trades)) * 100
        
        logger.debug(f"Win rate: {winning_trades}/{len(self.trades)} = {win_rate:.2f}%")
        
        return win_rate
    
    def profit_factor(self) -> float:
        """
        Calculate profit factor as ratio of gross profits to gross losses.
        
        **Validates: Requirement 8.2**
        
        Formula: gross_profits / gross_losses
        
        Returns:
            Profit factor (>1.0 is profitable, >2.0 is excellent)
        """
        gross_profits = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        gross_losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        
        if gross_losses == 0:
            # No losses - return infinity if there are profits, else 0
            return float('inf') if gross_profits > 0 else 0.0
        
        pf = gross_profits / gross_losses
        
        logger.debug(
            f"Profit factor: ${gross_profits:.2f} / ${gross_losses:.2f} = {pf:.2f}"
        )
        
        return pf
    
    def sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio using daily returns.
        
        **Validates: Requirement 8.3**
        
        Formula: (mean(excess_returns) / std(excess_returns)) * sqrt(252)
        where excess_returns = daily_returns - risk_free_rate/252
        
        Returns:
            Annualized Sharpe ratio (>1.0 is good, >1.5 is excellent)
        """
        if len(self.equity_curve) < 2:
            return 0.0
        
        # Calculate daily returns
        daily_returns = self.equity_curve.pct_change().dropna()
        
        if len(daily_returns) == 0 or daily_returns.std() == 0:
            return 0.0
        
        # Calculate excess returns (subtract risk-free rate)
        daily_risk_free = self.risk_free_rate / 252
        excess_returns = daily_returns - daily_risk_free
        
        # Annualize Sharpe ratio
        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252)
        
        logger.debug(
            f"Sharpe ratio: mean={excess_returns.mean():.6f}, "
            f"std={excess_returns.std():.6f}, sharpe={sharpe:.2f}"
        )
        
        return sharpe
    
    def max_drawdown(self) -> float:
        """
        Calculate maximum drawdown as largest peak-to-trough decline.
        
        **Validates: Requirement 8.4**
        
        Formula: max((peak - trough) / peak) * 100
        
        Returns:
            Maximum drawdown as percentage (0-100)
        """
        if len(self.equity_curve) < 2:
            return 0.0
        
        # Calculate running maximum (peak)
        cumulative_max = self.equity_curve.cummax()
        
        # Calculate drawdown at each point
        drawdown = (self.equity_curve - cumulative_max) / cumulative_max
        
        # Maximum drawdown is the most negative value
        max_dd = abs(drawdown.min()) * 100
        
        logger.debug(f"Maximum drawdown: {max_dd:.2f}%")
        
        return max_dd
    
    def avg_r_multiple(self) -> float:
        """
        Calculate average R-multiple across all trades.
        
        **Validates: Requirement 8.5**
        
        R-multiple measures profit/loss relative to initial risk.
        
        Returns:
            Average R-multiple (>1.0 means average trade exceeds risk)
        """
        r_multiples = [t.get('r_multiple', 0.0) for t in self.trades]
        
        if len(r_multiples) == 0:
            return 0.0
        
        avg_r = np.mean(r_multiples)
        
        logger.debug(f"Average R-multiple: {avg_r:.2f}R")
        
        return avg_r
    
    def expectancy(self) -> float:
        """
        Calculate expectancy as expected value per trade.
        
        **Validates: Requirement 8.6**
        
        Formula: (win_rate × avg_win) - (loss_rate × avg_loss)
        
        Returns:
            Expected profit per trade in dollars
        """
        if len(self.trades) == 0:
            return 0.0
        
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] < 0]
        
        if len(winning_trades) == 0 and len(losing_trades) == 0:
            return 0.0
        
        win_rate_decimal = len(winning_trades) / len(self.trades)
        loss_rate_decimal = len(losing_trades) / len(self.trades)
        
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades])) if losing_trades else 0.0
        
        exp = (win_rate_decimal * avg_win) - (loss_rate_decimal * avg_loss)
        
        logger.debug(
            f"Expectancy: ({win_rate_decimal:.2f} × ${avg_win:.2f}) - "
            f"({loss_rate_decimal:.2f} × ${avg_loss:.2f}) = ${exp:.2f}"
        )
        
        return exp
    
    def r_multiple_distribution(self) -> Dict[str, int]:
        """
        Calculate distribution of R-multiples across trades.
        
        **Validates: Requirement 8.7**
        
        Buckets:
        - 0-1R: Small wins/losses
        - 1-2R: Moderate wins
        - 2-5R: Good wins
        - 5-10R: Excellent wins
        - >10R: Home runs
        
        Returns:
            Dictionary with count of trades in each bucket
        """
        r_multiples = [t.get('r_multiple', 0.0) for t in self.trades]
        
        distribution = {
            '0-1R': len([r for r in r_multiples if 0 <= r < 1]),
            '1-2R': len([r for r in r_multiples if 1 <= r < 2]),
            '2-5R': len([r for r in r_multiples if 2 <= r < 5]),
            '5-10R': len([r for r in r_multiples if 5 <= r < 10]),
            '>10R': len([r for r in r_multiples if r >= 10]),
            '<0R': len([r for r in r_multiples if r < 0])  # Losses
        }
        
        logger.debug(f"R-multiple distribution: {distribution}")
        
        return distribution
    
    def monthly_returns(self) -> pd.Series:
        """
        Calculate monthly returns and identify best/worst months.
        
        **Validates: Requirement 8.8**
        
        Returns:
            Series of monthly return percentages indexed by month
        """
        if len(self.equity_curve) < 2:
            return pd.Series(dtype=float)
        
        # Resample equity curve to monthly (ME = month end)
        monthly_equity = self.equity_curve.resample('ME').last()
        
        # Calculate monthly returns
        monthly_ret = monthly_equity.pct_change().dropna() * 100
        
        if len(monthly_ret) > 0:
            logger.debug(
                f"Monthly returns: best={monthly_ret.max():.2f}%, "
                f"worst={monthly_ret.min():.2f}%, mean={monthly_ret.mean():.2f}%"
            )
        
        return monthly_ret
    
    def _zero_metrics(self) -> PerformanceMetrics:
        """Return zero metrics when no trades available."""
        return PerformanceMetrics(
            win_rate=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            avg_r_multiple=0.0,
            expectancy=0.0,
            r_multiple_distribution={'0-1R': 0, '1-2R': 0, '2-5R': 0, '5-10R': 0, '>10R': 0, '<0R': 0},
            monthly_returns=pd.Series(dtype=float),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            gross_profits=0.0,
            gross_losses=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            best_month=0.0,
            worst_month=0.0
        )
