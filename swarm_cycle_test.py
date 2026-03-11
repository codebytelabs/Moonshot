#!/usr/bin/env python3

import requests
import json
import time
import sys
from datetime import datetime

class SwarmCycleTester:
    def __init__(self):
        self.base_url = "https://swarm-command-center.preview.emergentagent.com"
        
    def api_call(self, method: str, endpoint: str, data: dict = None):
        """Make API call and return response"""
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ API Error ({endpoint}): {str(e)}")
            return None

    def test_swarm_cycle(self):
        """Test complete swarm cycle as specified in requirements"""
        print("🔥 APEX-SWARM Cycle Test Started")
        print("=" * 60)
        
        # Step 1: Start the swarm
        print("\n🚀 Step 1: Starting swarm...")
        result = self.api_call("POST", "/api/swarm/start")
        if not result:
            print("❌ Failed to start swarm")
            return False
        
        print(f"✅ Swarm started: {result.get('status', 'unknown')}")
        
        # Step 2: Wait 40 seconds for full cycle (as specified)
        print(f"\n⏱️  Step 2: Waiting 40 seconds for full swarm cycle...")
        for i in range(40, 0, -5):
            print(f"   {i}s remaining...")
            time.sleep(5)
        
        # Step 3: Check agent logs (should have >5 entries)
        print(f"\n📋 Step 3: Checking agent logs...")
        logs = self.api_call("GET", "/api/agent-logs?limit=100")
        if not logs:
            print("❌ Failed to fetch agent logs")
            return False
            
        print(f"✅ Retrieved {len(logs)} log entries")
        
        # Count recent logs from the cycle
        now = datetime.now()
        recent_logs = []
        for log in logs:
            try:
                log_time = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
                if (now - log_time.replace(tzinfo=None)).total_seconds() < 300:  # Last 5 minutes
                    recent_logs.append(log)
            except:
                pass
        
        print(f"   Recent logs (last 5min): {len(recent_logs)}")
        if len(recent_logs) >= 5:
            print("✅ PASS: Found sufficient agent activity")
            # Show some sample logs
            for i, log in enumerate(recent_logs[:5]):
                print(f"   {i+1}. [{log['agent']}] {log['status']}: {log['message'][:60]}...")
        else:
            print("⚠️  WARNING: Limited agent activity detected")
        
        # Step 4: Check alpha hits (token discovery data)
        print(f"\n🎯 Step 4: Checking alpha hits...")
        hits = self.api_call("GET", "/api/alpha-hits?limit=50")
        if not hits:
            print("❌ Failed to fetch alpha hits")
            return False
            
        print(f"✅ Retrieved {len(hits)} alpha hits")
        if len(hits) > 0:
            print("✅ PASS: Token discovery data available")
            # Show sample hits
            for i, hit in enumerate(hits[:3]):
                symbol = hit.get('baseToken', {}).get('symbol', 'Unknown')
                chain = hit.get('chainId', 'unknown')
                score = hit.get('score', 0)
                print(f"   {i+1}. {symbol} on {chain} (Score: {score})")
        else:
            print("⚠️  No alpha hits found")
        
        # Step 5: Check trades (simulated trade entries)  
        print(f"\n💰 Step 5: Checking trades...")
        trades = self.api_call("GET", "/api/trades?limit=50")
        if not trades:
            print("❌ Failed to fetch trades")
            return False
            
        print(f"✅ Retrieved {len(trades)} trade entries")
        if len(trades) > 0:
            print("✅ PASS: Simulated trade entries available")
            # Show sample trades
            for i, trade in enumerate(trades[:3]):
                symbol = trade.get('symbol', 'Unknown')
                status = trade.get('status', 'Unknown')
                side = trade.get('side', 'Unknown')
                price = trade.get('price', '0')
                print(f"   {i+1}. {side} {symbol} @ ${price} (Status: {status})")
        else:
            print("⚠️  No trades found")
        
        # Step 6: Stop the swarm
        print(f"\n🛑 Step 6: Stopping swarm...")
        result = self.api_call("POST", "/api/swarm/stop")
        if not result:
            print("❌ Failed to stop swarm")
            return False
            
        print(f"✅ Swarm stopped: {result.get('status', 'unknown')}")
        
        # Final assessment
        print("\n" + "=" * 60)
        print("📊 SWARM CYCLE TEST RESULTS:")
        
        criteria_met = []
        if len(recent_logs) >= 5:
            criteria_met.append("✅ Agent logs show activity (>5 entries)")
        else:
            criteria_met.append("⚠️  Limited agent log activity")
            
        if len(hits) > 0:
            criteria_met.append("✅ Alpha hits contain token discovery data")
        else:
            criteria_met.append("❌ No alpha hits found")
            
        if len(trades) > 0:
            criteria_met.append("✅ Trades contain simulated entries")
        else:
            criteria_met.append("❌ No trade entries found")
        
        for criterion in criteria_met:
            print(f"   {criterion}")
        
        success = "❌" not in "".join(criteria_met)
        print(f"\n🎯 Overall Result: {'✅ PASS' if success else '❌ FAIL'}")
        
        return success

def main():
    tester = SwarmCycleTester()
    success = tester.test_swarm_cycle()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())