#!/usr/bin/env python3
"""
Quick Status Checker for Bot Validation

Run this anytime to check current bot status, positions, and recent performance.

Usage:
    python check_status.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from supabase import create_client

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def check_status():
    """Check current bot status and display summary."""
    
    # Initialize Supabase
    supabase_url = os.getenv('SUPABASE_PROJECT_URL')
    supabase_key = os.getenv('SUPABASE_ANON_PUBLIC')
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials not found in .env")
        return
    
    supabase = create_client(supabase_url, supabase_key)
    
    print("="*80)
    print("BOT STATUS CHECK")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check open positions
    print("--- OPEN POSITIONS ---")
    try:
        positions = supabase.table('positions').select('*').eq('status', 'open').execute()
        if positions.data:
            for pos in positions.data:
                print(f"  {pos['symbol']}: {pos['side']} | Entry: ${pos['entry_price']:.2f} | Size: {pos['position_size']:.4f}")
                print(f"    Stop: ${pos['stop_loss']:.2f} | Target: ${pos['take_profit']:.2f}")
        else:
            print("  No open positions")
    except Exception as e:
        print(f"  Error fetching positions: {e}")
    print()
    
    # Check recent trades (last 24 hours)
    print("--- RECENT TRADES (Last 24h) ---")
    try:
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        trades = supabase.table('trades').select('*').gte('entry_timestamp', yesterday).order('entry_timestamp', desc=True).execute()
        
        if trades.data:
            wins = sum(1 for t in trades.data if t.get('r_multiple', 0) > 0)
            total = len(trades.data)
            win_rate = (wins / total * 100) if total > 0 else 0
            
            print(f"  Total Trades: {total}")
            print(f"  Wins: {wins} | Losses: {total - wins}")
            print(f"  Win Rate: {win_rate:.1f}%")
            print()
            print("  Recent trades:")
            for trade in trades.data[:5]:
                r_mult = trade.get('r_multiple', 0)
                status = "✓" if r_mult > 0 else "✗"
                print(f"    {status} {trade['symbol']}: {r_mult:.2f}R | {trade['setup_type']}")
        else:
            print("  No trades in last 24 hours")
    except Exception as e:
        print(f"  Error fetching trades: {e}")
    print()
    
    # Check performance metrics
    print("--- PERFORMANCE METRICS (Last 7 Days) ---")
    try:
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        metrics = supabase.table('performance_metrics').select('*').gte('timestamp', week_ago).order('timestamp', desc=True).limit(1).execute()
        
        if metrics.data:
            m = metrics.data[0]
            print(f"  Win Rate: {m.get('win_rate', 0):.1%}")
            print(f"  Profit Factor: {m.get('profit_factor', 0):.2f}")
            print(f"  Sharpe Ratio: {m.get('sharpe_ratio', 0):.2f}")
            print(f"  Max Drawdown: {m.get('max_drawdown', 0):.1%}")
            print(f"  Total PnL: ${m.get('total_pnl', 0):.2f}")
        else:
            print("  No metrics available yet")
    except Exception as e:
        print(f"  Error fetching metrics: {e}")
    print()
    
    # Check edge cases
    print("--- EDGE CASES (Last 24h) ---")
    try:
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        edge_cases = supabase.table('edge_cases').select('*').gte('timestamp', yesterday).execute()
        
        if edge_cases.data:
            print(f"  Total: {len(edge_cases.data)}")
            categories = {}
            for ec in edge_cases.data:
                cat = ec.get('category', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1
            
            for cat, count in categories.items():
                print(f"    {cat}: {count}")
        else:
            print("  No edge cases (good!)")
    except Exception as e:
        print(f"  Error fetching edge cases: {e}")
    print()
    
    print("="*80)
    print()
    print("💡 TIP: Check Gate.io testnet dashboard for order verification:")
    print("   https://www.gate.io/testnet")
    print()
    print("💡 View detailed logs:")
    print("   tail -f logs/extended_validation_*.log")
    print()


if __name__ == "__main__":
    check_status()
