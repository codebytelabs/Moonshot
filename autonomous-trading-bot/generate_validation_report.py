#!/usr/bin/env python3
"""
Generate Validation Report

This script generates a comprehensive validation report comparing demo trading
performance to backtest expectations. It includes:
- Performance metrics comparison
- Variance analysis
- Edge case summary
- Risk assessment
- Go/no-go recommendation
- Equity curve and comparison charts

Usage:
    python generate_validation_report.py

Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8
"""
import asyncio
from datetime import datetime, timedelta
from loguru import logger
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.extended_validation_system import ExtendedValidationSystem, ValidationReport
from src.supabase_client import SupabaseStore
from src.gateio_testnet import GateIOTestnetConnector


async def generate_sample_report():
    """Generate a sample validation report using existing data."""
    logger.info("Generating validation report from demo trading data")
    
    # Initialize components
    store = SupabaseStore()
    exchange = GateIOTestnetConnector()
    
    # Create validation system (without bot for report generation only)
    validation_system = ExtendedValidationSystem(
        bot=None,  # Not needed for report generation
        exchange=exchange,
        store=store,
        duration_days=28
    )
    
    # Set start date (28 days ago)
    validation_system.start_date = datetime.now() - timedelta(days=28)
    
    # Load backtest metrics (example - replace with actual backtest results)
    backtest_metrics = {
        'total_trades': 120,
        'win_rate': 0.58,
        'profit_factor': 2.35,
        'sharpe_ratio': 1.82,
        'max_drawdown': 0.12,
        'total_pnl': 2450.00,
        'avg_r_multiple': 1.85
    }
    
    validation_system.backtest_metrics = backtest_metrics
    
    # Generate report
    logger.info("Generating comprehensive validation report...")
    report = await validation_system.generate_final_report()
    
    # Display summary
    print("\n" + "=" * 80)
    print("VALIDATION REPORT GENERATED")
    print("=" * 80)
    print(f"\nRecommendation: {report.go_no_go}")
    print(f"Notes: {report.recommendation_notes}")
    print(f"\nDemo Trades: {report.demo_metrics.get('total_trades', 0)}")
    print(f"Demo Win Rate: {report.demo_metrics.get('win_rate', 0):.2%}")
    print(f"Demo Profit Factor: {report.demo_metrics.get('profit_factor', 0):.2f}")
    print(f"Demo Sharpe Ratio: {report.demo_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"\nEdge Cases: {report.edge_case_summary.get('total_count', 0)}")
    print(f"Resolution Rate: {report.edge_case_summary.get('resolution_rate', 0):.1%}")
    print(f"\nRisk Level: {report.risk_assessment.get('risk_level', 'UNKNOWN')}")
    print(f"Recommended Capital: ${report.risk_assessment.get('recommended_starting_capital', 0):,.2f}")
    
    if report.equity_curve_chart_path:
        print(f"\nEquity Curve Chart: {report.equity_curve_chart_path}")
    if report.performance_comparison_chart_path:
        print(f"Performance Comparison Chart: {report.performance_comparison_chart_path}")
    
    print("\n" + "=" * 80)
    
    return report


async def generate_report_with_custom_metrics(
    backtest_metrics: dict,
    demo_start_date: datetime = None
):
    """
    Generate validation report with custom backtest metrics.
    
    Args:
        backtest_metrics: Expected metrics from backtest
        demo_start_date: Start date of demo trading period
    """
    logger.info("Generating validation report with custom metrics")
    
    # Initialize components
    store = SupabaseStore()
    exchange = GateIOTestnetConnector()
    
    # Create validation system
    validation_system = ExtendedValidationSystem(
        bot=None,
        exchange=exchange,
        store=store,
        duration_days=28
    )
    
    # Set start date
    if demo_start_date:
        validation_system.start_date = demo_start_date
    else:
        validation_system.start_date = datetime.now() - timedelta(days=28)
    
    # Set backtest metrics
    validation_system.backtest_metrics = backtest_metrics
    
    # Generate report
    report = await validation_system.generate_final_report()
    
    logger.info(f"Validation report generated: {report.go_no_go}")
    
    return report


def print_usage():
    """Print usage instructions."""
    print("""
Usage: python generate_validation_report.py

This script generates a comprehensive validation report from demo trading data.

The report includes:
- Executive Summary
- Backtest Results
- Demo Trading Results  
- Performance Comparison (variance analysis)
- Edge Cases Summary
- Risk Assessment
- Go/No-Go Recommendation
- Equity Curve Chart
- Performance Comparison Chart

Output:
- JSON report: ./reports/validation_report_YYYYMMDD_HHMMSS.json
- Text summary: ./reports/validation_summary_YYYYMMDD_HHMMSS.txt
- Charts: ./reports/charts/

Requirements:
- Demo trading data in database (trades table)
- Backtest metrics for comparison
- Supabase connection configured
""")


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print_usage()
        sys.exit(0)
    
    # Generate report
    try:
        report = asyncio.run(generate_sample_report())
        logger.success("Validation report generation complete!")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("Report generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error generating validation report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
